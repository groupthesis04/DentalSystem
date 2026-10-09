"""Patient booking records each SMS choice and preserves its purpose."""

import datetime as dt
import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone

from accounts.consent import (
    APPOINTMENT_SMS_CONSENT_PURPOSE,
    APPOINTMENT_SMS_NOTICE_VERSION,
    CLINIC_SMS_BOOKING_NOTICE_VERSION,
    CLINIC_SMS_CONSENT_PURPOSE,
    CLINIC_SMS_STAFF_NOTICE_VERSION,
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

    def test_patient_booking_requires_appointment_sms_agreement(self):
        for value in (None, False, "true", 1):
            with self.subTest(value=value):
                changes = {} if value is None else {"appointment_sms_consent": value}
                response = self.book(**changes)
                self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Appointment.objects.exists())
        self.assertFalse(PatientConsentRecord.objects.exists())
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.sms_consent)

    def test_declining_appointment_sms_does_not_create_a_booking(self):
        response = self.book(
            appointment_sms_consent=False, clinic_sms_consent=False,
            sms_consent_notice_version="",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Appointment.objects.exists())
        self.assertFalse(PatientConsentRecord.objects.exists())
        self.assertFalse(SmsMessage.objects.exists())

    def test_rejected_booking_preserves_prior_broad_grant(self):
        self.patient.sms_consent = True
        self.patient.sms_consent_at = timezone.now() - dt.timedelta(days=1)
        self.patient.sms_consent_method = "electronic"
        self.patient.save(update_fields=["sms_consent", "sms_consent_at", "sms_consent_method"])
        response = self.book(appointment_sms_consent=False, clinic_sms_consent=False)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Appointment.objects.exists())
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.sms_consent_method, "electronic")
        self.assertEqual(
            sms.enqueue_manual(self.patient, "manual:prior-broad", "Hello {PatientName}").status,
            "queued",
        )

    def test_legacy_appointment_without_explicit_decline_keeps_broad_scope(self):
        self.patient.sms_consent = True
        self.patient.sms_consent_at = timezone.now() - dt.timedelta(days=1)
        self.patient.sms_consent_method = "electronic"
        self.patient.save(update_fields=["sms_consent", "sms_consent_at", "sms_consent_method"])
        old = Appointment.objects.create(
            id="apt_legacy_scope", patient=self.patient, doctor=self.doctor,
            created_by=self.user, patient_name=self.patient.name,
            patient_phone=self.patient.phone, doctor_name=self.doctor.name,
            service_name=self.service.name, appointment_date=self.visit_date,
            appointment_time=dt.time(9), status="approved", source="patient",
        )
        self.assertFalse(old.appointment_sms_consent)
        self.assertFalse(old.appointment_sms_declined)
        self.assertEqual(sms.appointment_event(old, "approval").status, "queued")

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

    def test_optional_clinic_choice_records_separate_evidence_and_allows_clinic_sms(self):
        earlier = sms.enqueue_manual(
            self.patient, "manual:before-clinic-choice", "Hello {PatientName}",
        )
        self.assertEqual(earlier.status, "suppressed")
        response = self.book(
            appointment_sms_consent=True,
            clinic_sms_consent=True,
            sms_consent_notice_version=CLINIC_SMS_BOOKING_NOTICE_VERSION,
        )
        self.assertEqual(response.status_code, 201, response.content)
        item = Appointment.objects.get(pk=response.json()["appointment"]["id"])
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.sms_consent_method, "clinic_booking")
        self.assertEqual(self.patient.sms_consent_at, item.appointment_sms_consent_at)
        self.assertTrue(item.appointment_sms_consent)
        self.assertFalse(item.appointment_sms_declined)
        appointment_choice = PatientConsentRecord.objects.get(
            patient=self.patient, notice_version=APPOINTMENT_SMS_NOTICE_VERSION,
        )
        clinic_choice = PatientConsentRecord.objects.get(
            patient=self.patient, notice_version=CLINIC_SMS_BOOKING_NOTICE_VERSION,
        )
        self.assertEqual(PatientConsentRecord.objects.count(), 2)
        self.assertEqual(appointment_choice.purpose, APPOINTMENT_SMS_CONSENT_PURPOSE)
        self.assertEqual(clinic_choice.purpose, CLINIC_SMS_CONSENT_PURPOSE)
        self.assertTrue(clinic_choice.patient_choice_confirmed)
        self.assertEqual(clinic_choice.method, "booking")
        self.assertEqual(clinic_choice.actor, self.user)
        self.assertEqual(clinic_choice.recorded_at, item.appointment_sms_consent_at)
        earlier.refresh_from_db()
        self.assertEqual(earlier.status, "suppressed")
        self.assertEqual(
            sms.enqueue("balance", self.patient, "balance:clinic-choice", sms.message_context(self.patient)).status,
            "queued",
        )
        manual = sms.enqueue_manual(
            self.patient, "manual:clinic-choice", "Hello {PatientName}",
        )
        self.assertEqual(manual.status, "queued")
        with patch(
            "communications.sms.sms_provider.send",
            return_value=("philsms:clinic123", "submitted"),
        ) as send:
            sms.dispatch(manual.pk, timezone.now())
        send.assert_called_once()
        manual.refresh_from_db()
        self.assertEqual(manual.status, "submitted")

    def test_clinic_choice_needs_boolean_and_matching_notice(self):
        for appointment_choice, broad, version in (
            (False, True, CLINIC_SMS_BOOKING_NOTICE_VERSION),
            (True, "true", CLINIC_SMS_BOOKING_NOTICE_VERSION),
            (True, True, ""),
            (True, True, CLINIC_SMS_STAFF_NOTICE_VERSION),
            (True, False, CLINIC_SMS_BOOKING_NOTICE_VERSION),
        ):
            with self.subTest(appointment=appointment_choice, broad=broad, version=version):
                response = self.book(
                    appointment_sms_consent=appointment_choice,
                    clinic_sms_consent=broad,
                    sms_consent_notice_version=version,
                )
                self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Appointment.objects.exists())
        self.assertFalse(PatientConsentRecord.objects.exists())

    def test_patient_withdrawal_blocks_broad_clinic_sms(self):
        response = self.book(
            appointment_sms_consent=True, clinic_sms_consent=True,
            sms_consent_notice_version=CLINIC_SMS_BOOKING_NOTICE_VERSION,
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.patient.refresh_from_db()
        queued = sms.enqueue_manual(
            self.patient, "manual:before-withdrawal", "Hello {PatientName}",
        )
        self.assertEqual(queued.status, "queued")
        stop = self.client.patch(
            "/api/account/sms-preference",
            data=json.dumps({"sms_consent": False}), content_type="application/json",
        )
        self.assertEqual(stop.status_code, 200, stop.content)
        self.patient.refresh_from_db()
        queued.refresh_from_db()
        self.assertEqual(self.patient.sms_stop_reason, "patient_withdrew")
        self.assertEqual(queued.status, "suppressed")
        withdrawal = PatientConsentRecord.objects.get(
            patient=self.patient, action=PatientConsentRecord.Action.STOPPED,
        )
        self.assertTrue(withdrawal.patient_choice_confirmed)
        self.assertEqual(withdrawal.method, "electronic")
        self.assertEqual(withdrawal.actor, self.user)
        self.assertEqual(
            sms.enqueue_manual(self.patient, "manual:after-withdrawal", "Hello {PatientName}").status,
            "suppressed",
        )

    def test_generic_preference_patch_cannot_grant_broad_consent(self):
        response = self.client.patch(
            "/api/account/sms-preference",
            data=json.dumps({"sms_consent": True}), content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.sms_consent)
        self.assertFalse(PatientConsentRecord.objects.exists())

    def test_withdrawal_preserves_independent_operational_stop(self):
        self.patient.sms_stop_reason = "wrong_number"
        self.patient.sms_stop_reason_detail = "Number belongs to another patient."
        self.patient.save(update_fields=["sms_stop_reason", "sms_stop_reason_detail"])
        stop = self.client.patch(
            "/api/account/sms-preference",
            data=json.dumps({"sms_consent": False}), content_type="application/json",
        )
        self.assertEqual(stop.status_code, 200, stop.content)
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.sms_consent)
        self.assertEqual(self.patient.sms_stop_reason, "wrong_number")
        self.assertEqual(
            PatientConsentRecord.objects.get(patient=self.patient).stop_reason,
            "patient_withdrew",
        )

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

    def test_new_clinic_grant_survives_later_appointment_only_booking(self):
        first = self.book(
            appointment_sms_consent=True, clinic_sms_consent=True,
            sms_consent_notice_version=CLINIC_SMS_BOOKING_NOTICE_VERSION,
        )
        self.assertEqual(first.status_code, 201, first.content)
        self.patient.refresh_from_db()
        broad_at = self.patient.sms_consent_at
        AvailabilitySlot.objects.create(
            id="slot_later_sms", doctor=self.doctor,
            doctor_name=self.doctor.name,
            date=self.visit_date + dt.timedelta(days=1), time=dt.time(9),
        )
        self.payload.update({
            "date": (self.visit_date + dt.timedelta(days=1)).isoformat(),
            "booking_token": "booking_sms_later",
        })
        later = self.book(appointment_sms_consent=True, clinic_sms_consent=False)
        self.assertEqual(later.status_code, 201, later.content)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.sms_consent_method, "clinic_booking")
        self.assertEqual(self.patient.sms_consent_at, broad_at)
        self.assertEqual(PatientConsentRecord.objects.count(), 3)
        self.assertEqual(
            sms.enqueue_manual(self.patient, "manual:after-later-booking", "Hello {PatientName}").status,
            "queued",
        )

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

    def test_optional_staff_clinic_choice_allows_general_clinic_messages(self):
        self.client.force_login(self.doctor)
        response = self.book(
            patient_id=self.patient.pk,
            appointment_sms_consent=True,
            sms_consent_method="staff_in_person",
            clinic_sms_consent=True,
            sms_consent_notice_version=CLINIC_SMS_STAFF_NOTICE_VERSION,
        )
        self.assertEqual(response.status_code, 201, response.content)
        item = Appointment.objects.get(pk=response.json()["appointment"]["id"])
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.sms_consent_method, "clinic_staff")
        self.assertFalse(item.appointment_sms_declined)
        self.assertEqual(PatientConsentRecord.objects.filter(patient=self.patient).count(), 2)
        clinic_choice = PatientConsentRecord.objects.get(
            patient=self.patient, notice_version=CLINIC_SMS_STAFF_NOTICE_VERSION,
        )
        self.assertEqual(clinic_choice.purpose, CLINIC_SMS_CONSENT_PURPOSE)
        self.assertEqual(clinic_choice.method, "staff_in_person")
        self.assertEqual(clinic_choice.actor, self.doctor)
        self.assertEqual(clinic_choice.recorded_at, item.appointment_sms_consent_at)
        self.assertEqual(
            sms.enqueue("balance", self.patient, "balance:staff-clinic", sms.message_context(self.patient)).status,
            "queued",
        )
        self.assertEqual(
            sms.enqueue_manual(self.patient, "manual:staff-clinic", "Hello {PatientName}").status,
            "queued",
        )

    def test_staff_clinic_choice_requires_appointment_choice_and_correct_notice(self):
        self.client.force_login(self.doctor)
        for appointment_choice, broad, version in (
            (False, True, CLINIC_SMS_STAFF_NOTICE_VERSION),
            (True, True, ""),
            (True, True, CLINIC_SMS_BOOKING_NOTICE_VERSION),
            (True, False, CLINIC_SMS_STAFF_NOTICE_VERSION),
        ):
            with self.subTest(appointment=appointment_choice, broad=broad, version=version):
                response = self.book(
                    patient_id=self.patient.pk,
                    appointment_sms_consent=appointment_choice,
                    sms_consent_method="staff_in_person" if appointment_choice else "",
                    clinic_sms_consent=broad,
                    sms_consent_notice_version=version,
                )
                self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Appointment.objects.exists())
        self.assertFalse(PatientConsentRecord.objects.exists())

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

    def test_optional_clinic_choice_does_not_clear_operational_stop(self):
        self.patient.sms_stop_reason = "wrong_number"
        self.patient.save(update_fields=["sms_stop_reason"])
        response = self.book(
            appointment_sms_consent=True, clinic_sms_consent=True,
            sms_consent_notice_version=CLINIC_SMS_BOOKING_NOTICE_VERSION,
        )
        self.assertEqual(response.status_code, 201, response.content)
        item = Appointment.objects.get(pk=response.json()["appointment"]["id"])
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.sms_stop_reason, "wrong_number")
        self.assertEqual(PatientConsentRecord.objects.filter(patient=self.patient).count(), 2)
        self.assertEqual(SmsMessage.objects.get(appointment=item, rule_id="booking").status, "suppressed")
        self.assertEqual(
            sms.enqueue_manual(self.patient, "manual:operational-stop", "Hello {PatientName}").status,
            "suppressed",
        )

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
