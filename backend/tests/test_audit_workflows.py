"""Audit events emitted by clinical and SMS workflows."""

import datetime as dt
import json
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from accounts.audit_models import AuditEvent
from accounts.models import PatientProfile
from communications import sms
from records.models import TreatmentRecord
from scheduling.models import Appointment
from tests import test_django_api


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AuditWorkflowTests(TestCase):
    def setUp(self):
        test_django_api.DentalApiTests.setUp(self)
        self.client.force_login(self.doctor)

    def request_json(self, method, path, payload):
        return getattr(self.client, method)(
            path, data=json.dumps(payload), content_type="application/json"
        )

    def test_self_registration_records_creation_and_login_without_personal_details(self):
        payload = {
            "first_name": "Audit",
            "last_name": "Patient",
            "email": "self-register-audit@example.com",
            "phone": "09112223333",
            "birthdate": "2000-04-12",
            "password": "NewPatient123!",
            "role": "patient",
        }
        response = Client().post("/api/register", data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 201, response.content)
        profile = PatientProfile.objects.get(email=payload["email"])
        created = AuditEvent.objects.get(event="PATIENT_CREATED", target_id=profile.pk)
        login = AuditEvent.objects.get(event="LOGIN_SUCCESS", actor_id=profile.user_id)
        self.assertEqual(created.actor_id, profile.user_id)
        self.assertEqual(created.metadata, {"origin": "patient"})
        self.assertNotIn(payload["email"], str(created.metadata))
        self.assertNotIn(payload["phone"], str(login.metadata))

    def test_treatment_create_and_update_record_actor_and_stable_target(self):
        values = {
            "patient_id": self.profile.pk,
            "treatment_date": timezone.localdate().isoformat(),
            "procedures": [self.service.name],
            "diagnosis": "Routine examination",
        }
        created = self.request_json("post", "/api/records", values)
        self.assertEqual(created.status_code, 201, created.content)
        record_id = created.json()["record"]["id"]
        updated = self.request_json("patch", "/api/records", {**values, "id": record_id})
        self.assertEqual(updated.status_code, 200, updated.content)

        events = list(AuditEvent.objects.filter(target_type="treatment", target_id=record_id))
        self.assertEqual({event.event for event in events}, {"TREATMENT_CREATED", "TREATMENT_UPDATED"})
        self.assertEqual({event.actor_id for event in events}, {self.doctor.pk})
        self.assertTrue(all(event.metadata == {} for event in events))

    def test_treatment_deletion_keeps_an_audit_reference(self):
        record = TreatmentRecord.objects.create(
            id="rec_audit_delete",
            patient=self.profile,
            doctor=self.doctor,
            patient_name=self.profile.name,
            doctor_name=self.doctor.name,
            procedure=self.service.name,
            treatment_date=timezone.localdate(),
        )
        response = self.request_json("delete", "/api/records", {"id": record.pk})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(TreatmentRecord.objects.filter(pk=record.pk).exists())
        event = AuditEvent.objects.get(event="TREATMENT_DELETED", target_id=record.pk)
        self.assertEqual(event.actor_id, self.doctor.pk)

    def test_unlinked_patient_deletion_audits_affected_records(self):
        patient = PatientProfile.objects.create(
            id="pat_audit_delete", first_name="Audit", last_name="Delete",
            mobile_number="09112223333",
        )
        record = TreatmentRecord.objects.create(
            id="rec_audit_patient_delete", patient=patient,
            patient_name=patient.name, doctor_name=self.doctor.name,
            procedure=self.service.name, treatment_date=timezone.localdate(),
        )
        response = self.request_json("delete", "/api/patients", {"id": patient.pk})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(PatientProfile.objects.filter(pk=patient.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(event="PATIENT_DELETED", target_id=patient.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(event="TREATMENT_DELETED", target_id=record.pk).exists())

    def test_cancelled_appointment_records_the_actor_without_patient_details(self):
        appointment = Appointment.objects.create(
            id="apt_audit_cancel",
            patient=self.profile,
            doctor=self.doctor,
            patient_name=self.profile.name,
            doctor_name=self.doctor.name,
            service_name=self.service.name,
            appointment_date=self.visit_date,
            appointment_time=dt.time(9, 0),
            status="pending",
        )
        response = self.request_json(
            "patch", "/api/appointments", {"id": appointment.pk, "status": "cancelled"}
        )
        self.assertEqual(response.status_code, 200, response.content)
        event = AuditEvent.objects.get(event="APPOINTMENT_CANCELLED", target_id=appointment.pk)
        self.assertEqual(event.actor_id, self.doctor.pk)
        self.assertEqual(event.target_type, "appointment")
        self.assertEqual(event.metadata, {})

    def test_sms_gateway_acceptance_records_no_phone_or_message_body(self):
        self.profile.sms_consent = True
        self.profile.sms_consent_at = timezone.now()
        self.profile.save(update_fields=["sms_consent", "sms_consent_at"])
        TreatmentRecord.objects.create(
            id="rec_audit_balance",
            patient=self.profile,
            doctor=self.doctor,
            patient_name=self.profile.name,
            doctor_name=self.doctor.name,
            procedure=self.service.name,
            treatment_date=timezone.localdate(),
            amount_charged=1000,
            amount_paid=0,
            balance=1000,
        )
        item = sms.enqueue(
            "balance", self.profile, "audit:balance", sms.message_context(self.profile)
        )
        self.assertEqual(item.status, "queued")
        with patch("communications.sms_provider.send", return_value=("12345", "submitted")):
            sms.dispatch(item.pk, timezone.now())

        event = AuditEvent.objects.get(event="SMS_SENT", target_id=item.pk)
        self.assertIsNone(event.actor)
        self.assertEqual(event.metadata, {"origin": "system"})
        self.assertNotIn(self.profile.mobile_number, str(event.metadata))
        self.assertNotIn(self.profile.name, str(event.metadata))
