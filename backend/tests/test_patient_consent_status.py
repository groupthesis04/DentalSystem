"""Consent and patient account controls keep clinical history intact."""

import datetime as dt
from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import PatientProfile, User
from communications.models import SmsMessage
from communications import sms
from records.models import TreatmentRecord
from scheduling.models import Appointment


class PatientConsentStatusTests(TestCase):
    def setUp(self):
        cache.clear()
        self.doctor = User.objects.create_user(
            email="doctor-consent@example.com", password="Doctor123!",
            name="Dr. Santos", role="doctor", is_staff=True,
        )
        self.user = User.objects.create_user(
            email="patient-consent@example.com", password="Patient123!",
            name="Pat One", phone="09123456789", role="patient",
        )
        self.patient = PatientProfile.objects.create(
            id="pat_consent", user=self.user, first_name="Pat", last_name="One",
            email=self.user.email, mobile_number=self.user.phone,
            privacy_consent_given=True, privacy_consent_at=timezone.now(),
            privacy_version="registration-2026-10-01", sms_consent=True,
            sms_consent_at=timezone.now(),
        )
        self.doctor_client = Client()
        self.doctor_client.force_login(self.doctor)
        self.patient_client = Client()
        self.patient_client.force_login(self.user)

    def test_registration_requires_privacy_choice_and_records_separate_sms_choice(self):
        payload = {
            "first_name": "New", "last_name": "Patient",
            "email": "new-consent@example.com", "phone": "09112223333",
            "birthdate": "2000-04-12", "password": "NewPatient123!",
            "role": "patient", "privacy_version": "registration-2026-10-01",
            "sms_consent": False,
        }
        missing = self.client.post("/api/register", data=payload, content_type="application/json")
        self.assertEqual(missing.status_code, 400)
        self.assertFalse(User.objects.filter(email=payload["email"]).exists())

        payload["privacy_consent_given"] = True
        response = self.client.post("/api/register", data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 201, response.content)
        profile = User.objects.get(email=payload["email"]).patient_profile
        self.assertTrue(profile.privacy_consent_given)
        self.assertIsNotNone(profile.privacy_consent_at)
        self.assertEqual(profile.privacy_version, payload["privacy_version"])
        self.assertIs(profile.sms_consent, False)
        self.assertIsNotNone(profile.sms_consent_at)

    def test_disable_revokes_sessions_and_enable_keeps_appointments_and_treatments(self):
        appointment = Appointment.objects.create(
            id="apt_consent", patient=self.patient, patient_name=self.patient.name,
            patient_email=self.patient.email, patient_phone=self.patient.phone,
            doctor_name=self.doctor.name, service_name="Cleaning",
            appointment_date=dt.date.today() + dt.timedelta(days=7),
            appointment_time=dt.time(9), status="pending", source="manual",
        )
        record = TreatmentRecord.objects.create(
            id="rec_consent", patient=self.patient, appointment=appointment,
            patient_name=self.patient.name, doctor_name=self.doctor.name,
            treatment_date=dt.date.today(), procedure="Cleaning",
            amount_charged=1000, amount_paid=200, balance=800,
        )
        self.assertIsNotNone(self.patient_client.get("/api/session").json()["user"])
        response = self.doctor_client.patch(
            "/api/patients",
            data={"action": "account_status", "id": self.patient.id, "is_active": False},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIs(response.json()["patient"]["account_active"], False)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertIsNone(self.patient_client.get("/api/session").json()["user"])
        login = self.patient_client.post(
            "/api/login",
            data={"email": self.user.email, "password": "Patient123!"},
            content_type="application/json",
        )
        self.assertEqual(login.status_code, 403)
        self.assertIn("disabled", login.json()["error"].lower())
        self.assertTrue(Appointment.objects.filter(pk=appointment.pk, patient=self.patient).exists())
        self.assertTrue(TreatmentRecord.objects.filter(pk=record.pk, patient=self.patient).exists())

        response = self.doctor_client.patch(
            "/api/patients",
            data={"action": "account_status", "id": self.patient.id, "is_active": True},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertTrue(Appointment.objects.filter(pk=appointment.pk).exists())
        self.assertTrue(TreatmentRecord.objects.filter(pk=record.pk).exists())

    def test_patient_opt_out_suppresses_queued_and_future_sms(self):
        queued = sms.enqueue("booking", self.patient, "consent:queued", sms.message_context(self.patient))
        self.assertEqual(queued.status, "queued")
        response = self.patient_client.patch(
            "/api/account/sms-preference", data={"sms_consent": False},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        queued.refresh_from_db()
        self.assertEqual(queued.status, "suppressed")
        future = sms.enqueue("booking", self.patient, "consent:future", sms.message_context(self.patient))
        self.assertEqual(future.status, "suppressed")
        self.patient.refresh_from_db()
        self.assertIs(self.patient.sms_consent, False)
        self.assertTrue(SmsMessage.objects.filter(patient=self.patient, status="suppressed").exists())

        self.patient.sms_consent = None
        self.patient.save(update_fields=["sms_consent"])
        legacy = sms.enqueue("booking", self.patient, "consent:legacy", sms.message_context(self.patient))
        self.assertEqual(legacy.status, "queued")

    def test_send_time_rechecks_opt_out_before_provider_call(self):
        queued = sms.enqueue("booking", self.patient, "consent:dispatch", sms.message_context(self.patient))
        self.patient.sms_consent = False
        self.patient.save(update_fields=["sms_consent"])
        with patch("communications.sms.sms_provider.send") as send:
            sms.dispatch(queued.pk, timezone.now())
        send.assert_not_called()
        queued.refresh_from_db()
        self.assertEqual(queued.status, "suppressed")
        self.assertIn("consent", queued.error)

    def test_only_doctor_can_change_account_status(self):
        response = self.patient_client.patch(
            "/api/patients",
            data={"action": "account_status", "id": self.patient.id, "is_active": False},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
