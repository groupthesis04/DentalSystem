"""The activity log is doctor-only and never stores caller-provided PHI."""

import datetime as dt
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from accounts.audit import record_audit_event
from accounts.audit_models import AuditEvent
from accounts.models import PatientAccountVerification, PatientProfile, User
from accounts.views import send_verification_code, verification_token_hash
from communications.sms_provider import SmsProviderError


class AuditLogTests(TestCase):
    def setUp(self):
        self.doctor = User.objects.create_user(
            email="doctor@example.com",
            password="Doctor123!",
            name="Dr. Test",
            role="doctor",
        )
        self.patient = User.objects.create_user(
            email="patient@example.com",
            password="Patient123!",
            name="Test Patient",
            role="patient",
        )

    def test_event_writer_stores_only_allowlisted_metadata(self):
        row = record_audit_event(
            "PASSWORD_CHANGED",
            actor=self.doctor,
            target=self.doctor,
            metadata={
                "password": "NeverStoreThis123!",
                "otp": "123456",
                "patient_name": "Sensitive Name",
                "channel": "email",
                "origin": "doctor",
            },
        )
        self.assertEqual(row.metadata, {"channel": "email", "origin": "doctor"})
        self.assertEqual(row.actor_id_snapshot, self.doctor.pk)
        self.assertEqual(row.target_type, "account")
        self.assertEqual(row.target_id, self.doctor.pk)
        self.assertNotIn("NeverStoreThis123!", str(row.__dict__))

    def test_only_doctor_can_read_bounded_filtered_events(self):
        record_audit_event("LOGIN_FAILED")
        record_audit_event("PATIENT_UPDATED", actor=self.doctor)
        self.assertEqual(self.client.get("/api/account/activity-log").status_code, 403)
        self.client.force_login(self.patient)
        self.assertEqual(self.client.get("/api/account/activity-log").status_code, 403)
        self.client.force_login(self.doctor)
        response = self.client.get("/api/account/activity-log?event=LOGIN_FAILED&page=1")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(len(body["events"]), 1)
        self.assertEqual(body["events"][0]["actor"], "Unknown")
        self.assertEqual(body["events"][0]["result"], "failed")
        self.assertEqual(body["page_size"], 25)
        self.assertEqual(self.client.get("/api/account/activity-log?event=BOGUS").status_code, 400)
        self.assertEqual(self.client.get("/api/account/activity-log?page=0").status_code, 400)

    def test_unknown_event_is_rejected_without_a_database_write(self):
        with self.assertRaises(ValueError):
            record_audit_event("PASSWORD_DUMPED", metadata={"secret": "bad"})
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_account_verification_sms_audit_omits_code_and_uncertain_sends(self):
        profile = PatientProfile.objects.create(id="pat_1", first_name="Jane", last_name="Doe")
        token = "verification-token"
        PatientAccountVerification.objects.create(
            patient=profile,
            token_hash=verification_token_hash(token),
            phone_number="09171234567",
            email="jane@example.com",
            first_name="Jane",
            last_name="Doe",
            birthdate=dt.date(2000, 1, 1),
            expires_at=timezone.now() + dt.timedelta(minutes=5),
        )
        with patch("accounts.views.sms_provider.send", return_value=("123", "submitted")):
            response = send_verification_code("09171234567", token, "987654")
        self.assertEqual(response.status_code, 202)
        row = AuditEvent.objects.get(event="SMS_SENT")
        self.assertEqual(row.target_type, "patient")
        self.assertEqual(row.target_id, profile.pk)
        self.assertEqual(row.metadata, {"origin": "system", "channel": "sms"})
        self.assertNotIn("987654", str(row.__dict__))
        self.assertNotIn("09171234567", str(row.__dict__))

        with patch("accounts.views.sms_provider.send", side_effect=SmsProviderError("uncertain", uncertain=True)):
            response = send_verification_code("09171234567", token, "123456")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(AuditEvent.objects.filter(event="SMS_SENT").count(), 1)
