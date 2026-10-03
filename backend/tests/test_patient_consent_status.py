"""Consent and patient account controls keep clinical history intact."""

import datetime as dt
from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import PatientConsentRecord, PatientProfile, User
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

    @patch("accounts.views.validate_email_address", return_value={
        "valid": True, "status": "valid", "message": "Email address is valid.",
    })
    def test_registration_without_choice_fields_does_not_fabricate_consent(self, _email_validation):
        payload = {
            "first_name": "New", "last_name": "Patient",
            "email": "new-consent@example.com", "phone": "09112223333",
            "birthdate": "2000-04-12", "password": "NewPatient123!",
            "role": "patient",
        }
        response = self.client.post("/api/register", data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 201, response.content)
        profile = User.objects.get(email=payload["email"]).patient_profile
        self.assertFalse(profile.privacy_consent_given)
        self.assertIsNone(profile.privacy_consent_at)
        self.assertEqual(profile.privacy_version, "")
        self.assertIs(profile.sms_consent, False)
        self.assertIsNone(profile.sms_consent_at)
        self.assertFalse(profile.consent_records.exists())
        doctor_view = self.doctor_client.get("/api/patients")
        self.assertEqual(doctor_view.status_code, 200)
        patient = next(
            item for item in doctor_view.json()["patients"] if item["id"] == profile.pk
        )
        self.assertNotIn("consent", patient)

    @patch("accounts.views.validate_email_address", return_value={
        "valid": True, "status": "valid", "message": "Email address is valid.",
    })
    def test_legacy_registration_choice_fields_are_ignored(self, _email_validation):
        response = self.client.post(
            "/api/register",
            data={
                "first_name": "Stale", "last_name": "Client",
                "email": "stale-client@example.com", "phone": "09112224444",
                "birthdate": "2000-04-12", "password": "NewPatient123!",
                "privacy_consent_given": True,
                "privacy_version": "registration-2026-10-01",
                "sms_consent": True,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        profile = User.objects.get(email="stale-client@example.com").patient_profile
        self.assertFalse(profile.privacy_consent_given)
        self.assertIsNone(profile.privacy_consent_at)
        self.assertFalse(profile.sms_consent)
        self.assertIsNone(profile.sms_consent_at)
        self.assertFalse(profile.consent_records.exists())

    def test_admin_created_patient_has_no_consent_section(self):
        clinic_profile = PatientProfile.objects.create(
            id="pat_unlinked_consent", first_name="Clinic", last_name="Patient",
            email="clinic-patient@example.com", mobile_number="09112345678",
        )
        response = self.doctor_client.get("/api/patients")
        self.assertEqual(response.status_code, 200)
        patient = next(
            item for item in response.json()["patients"] if item["id"] == clinic_profile.pk
        )
        self.assertNotIn("consent", patient)

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
        self.assertEqual(self.patient.sms_stop_reason, "patient_withdrew")
        self.assertEqual(self.patient.sms_consent_recorded_by, self.user)
        self.assertTrue(SmsMessage.objects.filter(patient=self.patient, status="suppressed").exists())
        self.assertEqual(
            PatientConsentRecord.objects.filter(
                patient=self.patient,
                kind=PatientConsentRecord.Kind.SMS,
                action=PatientConsentRecord.Action.STOPPED,
                actor=self.user,
            ).count(),
            1,
        )

        self.patient.sms_consent = None
        self.patient.save(update_fields=["sms_consent"])
        legacy = sms.enqueue("booking", self.patient, "consent:legacy", sms.message_context(self.patient))
        self.assertEqual(legacy.status, "suppressed")

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

    def test_doctor_cannot_change_sms_preference_from_patient_management(self):
        response = self.doctor_client.patch(
            "/api/patients",
            data={
                "action": "sms_consent", "id": self.patient.pk,
                "sms_consent": True, "consent_method": "verbal",
                "patient_choice_confirmed": True,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.sms_consent)
        self.assertFalse(PatientConsentRecord.objects.filter(patient=self.patient).exists())
        self.assertEqual(
            self.doctor_client.get("/api/patients/consent-history", {"id": self.patient.pk}).status_code,
            404,
        )

    def test_not_recorded_sms_suppresses_enqueued_and_existing_queued_messages(self):
        self.patient.sms_consent = None
        self.patient.sms_consent_at = None
        self.patient.save(update_fields=["sms_consent", "sms_consent_at"])
        self.assertFalse(self.patient.consent_records.exists())
        item = sms.enqueue("booking", self.patient, "consent:unknown", sms.message_context(self.patient))
        self.assertEqual(item.status, "suppressed")
        queued = sms.enqueue("booking", self.patient, "consent:unknown:queued", sms.message_context(self.patient))
        SmsMessage.objects.filter(pk=queued.pk).update(status="queued", error="")
        with patch("communications.sms.sms_provider.send") as send:
            sms.dispatch(queued.pk, timezone.now())
        send.assert_not_called()
        queued.refresh_from_db()
        self.assertEqual(queued.status, "suppressed")
