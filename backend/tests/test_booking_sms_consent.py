"""Patient booking consent is explicit, durable, and limited to appointment SMS."""

import datetime as dt
import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone

from accounts.consent import (
    APPOINTMENT_SMS_CONSENT_PURPOSE,
    APPOINTMENT_SMS_NOTICE_VERSION,
    STAFF_APPOINTMENT_SMS_CONSENT_PURPOSE,
    STAFF_APPOINTMENT_SMS_NOTICE_VERSION,
)
from accounts.models import PatientConsentRecord, PatientProfile, User
from clinic.models import Service
from communications import sms
from communications.models import SmsMessage
from scheduling.models import Appointment, AvailabilitySlot


class BookingSmsConsentTests(TestCase):
    def setUp(self):
        cache.clear()
        self.doctor = User.objects.create_user(
            email="booking-doctor@example.com", password="TestDoctor123!",
            name="Dr. Booking", role="doctor",
        )
        self.user = User.objects.create_user(
            email="booking-patient@example.com", password="TestPatient123!",
            name="Booking Patient", role="patient", phone="09123456789",
        )
        self.patient = PatientProfile.objects.create(
            id="pat_booking_sms", user=self.user, first_name="Booking",
            last_name="Patient", email=self.user.email,
            mobile_number=self.user.phone,
        )
        self.service = Service.objects.create(
            id="svc_booking_sms", name="Oral Prophylaxis",
            description="Dental cleaning.",
        )
        self.visit_date = dt.date.today() + dt.timedelta(days=7)
        AvailabilitySlot.objects.create(
            id="slot_booking_sms", doctor=self.doctor,
            doctor_name=self.doctor.name, date=self.visit_date,
            time=dt.time(9),
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.payload = {
            "doctor": self.doctor.name,
            "service": self.service.name,
            "date": self.visit_date.isoformat(),
            "time": "09:00",
            "booking_token": "booking_sms_once",
        }

    def book(self, **changes):
        return self.client.post(
            "/api/appointments",
            data=json.dumps({**self.payload, **changes}),
            content_type="application/json",
        )

    def test_patient_booking_requires_an_explicit_boolean_agreement(self):
        for value in (None, False, "true", 1):
            with self.subTest(value=value):
                changes = {} if value is None else {"appointment_sms_consent": value}
                response = self.book(**changes)
                self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Appointment.objects.exists())
        self.assertFalse(PatientConsentRecord.objects.exists())
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.sms_consent)

    def test_agreement_is_saved_with_appointment_and_booking_message(self):
        response = self.book(appointment_sms_consent=True)
        self.assertEqual(response.status_code, 201, response.content)
        item = Appointment.objects.get(pk=response.json()["appointment"]["id"])
        self.assertTrue(item.appointment_sms_consent)
        self.assertIsNotNone(item.appointment_sms_consent_at)
        self.assertEqual(
            response.json()["appointment"]["appointment_sms_consent_at"],
            item.appointment_sms_consent_at.isoformat(),
        )
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.sms_consent)
        self.assertEqual(self.patient.sms_consent_at, item.appointment_sms_consent_at)
        self.assertEqual(self.patient.sms_consent_method, "booking")
        choice = PatientConsentRecord.objects.get(patient=self.patient)
        self.assertTrue(choice.patient_choice_confirmed)
        self.assertTrue(choice.consent_given)
        self.assertEqual(choice.method, "booking")
        self.assertEqual(choice.purpose, APPOINTMENT_SMS_CONSENT_PURPOSE)
        self.assertEqual(choice.notice_version, APPOINTMENT_SMS_NOTICE_VERSION)
        self.assertEqual(choice.recorded_at, item.appointment_sms_consent_at)
        self.assertEqual(
            SmsMessage.objects.get(appointment=item, rule_id="booking").status,
            "queued",
        )

        replay = self.book(appointment_sms_consent=True)
        self.assertEqual(replay.status_code, 200, replay.content)
        self.assertTrue(replay.json()["replayed"])
        self.assertEqual(Appointment.objects.count(), 1)
        self.assertEqual(PatientConsentRecord.objects.count(), 1)
        self.assertEqual(SmsMessage.objects.filter(appointment=item, rule_id="booking").count(), 1)

        # Old saved drafts may retry without the new field. A replay does not
        # create another appointment or consent record.
        old_replay = self.book()
        self.assertEqual(old_replay.status_code, 200, old_replay.content)
        self.assertTrue(old_replay.json()["replayed"])
        self.assertEqual(PatientConsentRecord.objects.count(), 1)

    def test_booking_only_choice_does_not_authorize_payment_or_manual_sms(self):
        response = self.book(appointment_sms_consent=True)
        self.assertEqual(response.status_code, 201, response.content)
        item = Appointment.objects.get(pk=response.json()["appointment"]["id"])
        balance = sms.enqueue(
            "balance", self.patient, "balance:booking-scope",
            sms.message_context(self.patient),
        )
        self.assertEqual(balance.status, "suppressed")
        self.assertIn("this appointment only", balance.error)
        manual = sms.enqueue_manual(
            self.patient, "manual:booking-scope", "Hello {PatientName}", actor=self.doctor,
        )
        self.assertEqual(manual.status, "suppressed")

        # Recheck the scope when the worker sends, including previously queued rows.
        SmsMessage.objects.filter(pk=balance.pk).update(status="queued", error="")
        with patch("communications.sms.sms_provider.send") as send:
            sms.dispatch(balance.pk, timezone.now())
        send.assert_not_called()
        balance.refresh_from_db()
        self.assertEqual(balance.status, "suppressed")
        self.assertEqual(SmsMessage.objects.get(appointment=item, rule_id="booking").status, "queued")

        # An old appointment cannot borrow consent from this new booking.
        old = Appointment.objects.create(
            id="apt_without_booking_consent", patient=self.patient,
            doctor=self.doctor, created_by=self.user,
            patient_name=self.patient.name, patient_phone=self.patient.phone,
            doctor_name=self.doctor.name, service_name=self.service.name,
            appointment_date=self.visit_date + dt.timedelta(days=1),
            appointment_time=dt.time(9), status="approved", source="patient",
        )
        old_notice = sms.appointment_event(old, "approval")
        self.assertEqual(old_notice.status, "suppressed")
        SmsMessage.objects.filter(pk=old_notice.pk).update(status="queued", error="")
        with patch("communications.sms.sms_provider.send") as send:
            sms.dispatch(old_notice.pk, timezone.now())
        send.assert_not_called()
        old_notice.refresh_from_db()
        self.assertEqual(old_notice.status, "suppressed")

    def test_fresh_booking_grant_replaces_old_patient_withdrawal(self):
        self.patient.sms_consent = False
        self.patient.sms_consent_at = timezone.now()
        self.patient.sms_stop_reason = "patient_withdrew"
        self.patient.save(update_fields=["sms_consent", "sms_consent_at", "sms_stop_reason"])
        response = self.book(appointment_sms_consent=True)
        self.assertEqual(response.status_code, 201, response.content)
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.sms_consent)
        self.assertEqual(self.patient.sms_consent_method, "booking")
        self.assertEqual(self.patient.sms_stop_reason, "")

    def test_operational_stop_does_not_block_booking_or_get_cleared(self):
        self.patient.sms_stop_reason = "wrong_number"
        self.patient.save(update_fields=["sms_stop_reason"])
        response = self.book(appointment_sms_consent=True)
        self.assertEqual(response.status_code, 201, response.content)
        item = Appointment.objects.get(pk=response.json()["appointment"]["id"])
        self.assertTrue(item.appointment_sms_consent)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.sms_stop_reason, "wrong_number")
        self.assertEqual(SmsMessage.objects.get(appointment=item, rule_id="booking").status, "suppressed")

    def test_existing_broad_grant_remains_broad(self):
        earlier = timezone.now() - dt.timedelta(days=1)
        self.patient.sms_consent = True
        self.patient.sms_consent_at = earlier
        self.patient.sms_consent_method = "electronic"
        self.patient.save(update_fields=["sms_consent", "sms_consent_at", "sms_consent_method"])
        response = self.book(appointment_sms_consent=True)
        self.assertEqual(response.status_code, 201, response.content)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.sms_consent_method, "electronic")
        self.assertEqual(self.patient.sms_consent_at, earlier)
        self.assertEqual(PatientConsentRecord.objects.get().method, "booking")
        balance = sms.enqueue("balance", self.patient, "balance:broad", sms.message_context(self.patient))
        self.assertEqual(balance.status, "queued")

    def test_doctor_booking_does_not_require_or_claim_patient_agreement(self):
        self.client.force_login(self.doctor)
        response = self.book(patient_id=self.patient.pk)
        self.assertEqual(response.status_code, 201, response.content)
        item = Appointment.objects.get(pk=response.json()["appointment"]["id"])
        self.assertEqual(item.source, "manual")
        self.assertFalse(item.appointment_sms_consent)
        self.assertIsNone(item.appointment_sms_consent_at)
        self.assertFalse(PatientConsentRecord.objects.exists())

    def test_staff_attested_walk_in_consent_is_recorded_and_appointment_scoped(self):
        self.client.force_login(self.doctor)
        response = self.book(
            patient_id=self.patient.pk,
            appointment_sms_consent=True,
            sms_consent_method="staff_in_person",
        )
        self.assertEqual(response.status_code, 201, response.content)
        item = Appointment.objects.get(pk=response.json()["appointment"]["id"])
        self.assertTrue(item.appointment_sms_consent)
        self.assertIsNotNone(item.appointment_sms_consent_at)
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.sms_consent)
        # A staff-recorded appointment choice must not enable general clinic SMS.
        self.assertEqual(self.patient.sms_consent_method, "booking")
        choice = PatientConsentRecord.objects.get(patient=self.patient)
        self.assertTrue(choice.patient_choice_confirmed)
        self.assertEqual(choice.method, "staff_in_person")
        self.assertEqual(choice.actor, self.doctor)
        self.assertEqual(choice.actor_role, "doctor")
        self.assertEqual(choice.purpose, STAFF_APPOINTMENT_SMS_CONSENT_PURPOSE)
        self.assertEqual(choice.notice_version, STAFF_APPOINTMENT_SMS_NOTICE_VERSION)
        self.assertEqual(choice.recorded_at, item.appointment_sms_consent_at)
        self.assertEqual(SmsMessage.objects.get(appointment=item, rule_id="walk_in").status, "queued")
        self.assertEqual(
            sms.enqueue_manual(self.patient, "manual:staff-scope", "Hello {PatientName}").status,
            "suppressed",
        )

    def test_staff_sms_attestation_requires_explicit_boolean_and_method(self):
        self.client.force_login(self.doctor)
        for consent, method in ((True, None), (True, ""), (True, "booking"),
                                (True, "electronic"), ("true", "staff_phone"),
                                (False, "staff_phone"), (True, [])):
            with self.subTest(consent=consent, method=method):
                changes = {"patient_id": self.patient.pk, "appointment_sms_consent": consent}
                if method is not None:
                    changes["sms_consent_method"] = method
                response = self.book(**changes)
                self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Appointment.objects.exists())
        self.assertFalse(PatientConsentRecord.objects.exists())

    def test_staff_consented_walk_in_reaches_provider_without_real_sms(self):
        self.client.force_login(self.doctor)
        response = self.book(
            patient_id=self.patient.pk,
            appointment_sms_consent=True,
            sms_consent_method="staff_in_person",
        )
        self.assertEqual(response.status_code, 201, response.content)
        item = Appointment.objects.get(pk=response.json()["appointment"]["id"])
        message = SmsMessage.objects.get(appointment=item, rule_id="walk_in")
        self.assertEqual(message.status, "queued")
        with patch(
            "communications.sms.sms_provider.send",
            return_value=("philsms:walkin123", "submitted"),
        ) as send:
            sms.dispatch(message.pk, timezone.now())
        send.assert_called_once()
        self.assertEqual(send.call_args.args[0], "639123456789")
        message.refresh_from_db()
        self.assertEqual(message.provider_id, "philsms:walkin123")
        self.assertEqual(message.status, "submitted")
        self.assertEqual(message.attempts, 1)

    def test_staff_phone_attestation_does_not_clear_operational_stop(self):
        self.patient.sms_stop_reason = "wrong_number"
        self.patient.save(update_fields=["sms_stop_reason"])
        self.client.force_login(self.doctor)
        response = self.book(
            patient_id=self.patient.pk,
            appointment_sms_consent=True,
            sms_consent_method="staff_phone",
        )
        self.assertEqual(response.status_code, 201, response.content)
        item = Appointment.objects.get(pk=response.json()["appointment"]["id"])
        self.assertTrue(item.appointment_sms_consent)
        self.assertEqual(PatientConsentRecord.objects.get().method, "staff_phone")
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.sms_stop_reason, "wrong_number")
        self.assertEqual(SmsMessage.objects.get(appointment=item, rule_id="walk_in").status, "suppressed")

    def test_staff_attestation_rejects_an_invalid_patient_mobile(self):
        self.patient.mobile_number = ""
        self.patient.phone_number = ""
        self.patient.save(update_fields=["mobile_number", "phone_number"])
        self.client.force_login(self.doctor)
        response = self.book(
            patient_id=self.patient.pk,
            appointment_sms_consent=True,
            sms_consent_method="staff_phone",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Appointment.objects.exists())
        self.assertFalse(PatientConsentRecord.objects.exists())

    def test_staff_can_record_agreement_for_new_walk_in_patient(self):
        self.client.force_login(self.doctor)
        response = self.book(
            patient_id="", name="Walk In Patient", phone="09171234567",
            appointment_sms_consent=True, sms_consent_method="staff_in_person",
        )
        self.assertEqual(response.status_code, 201, response.content)
        item = Appointment.objects.get(pk=response.json()["appointment"]["id"])
        self.assertTrue(item.appointment_sms_consent)
        self.assertEqual(PatientConsentRecord.objects.get(patient=item.patient).actor, self.doctor)
        self.assertEqual(SmsMessage.objects.get(appointment=item, rule_id="walk_in").status, "queued")
