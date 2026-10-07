import datetime as dt
import json
import uuid
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError

from django.core.cache import cache
from django.db import transaction
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from communications import sms, sms_provider
from communications.models import SmsBalanceSchedule, SmsMessage, SmsRule, SmsTemplate, SmsWorker
from records.models import TreatmentRecord
from scheduling.models import Appointment
from tests import test_django_api


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"], SMS_ENABLED=True, SEMAPHORE_API_KEY="fake-key")
class SmsTests(TestCase):
    def setUp(self):
        test_django_api.DentalApiTests.setUp(self)
        cache.clear()
        # These provider tests exercise delivery after a patient has opted in.
        self.profile.sms_consent = True
        self.profile.sms_consent_at = timezone.now()
        self.profile.save(update_fields=["sms_consent", "sms_consent_at"])
        sms.ensure_rules()
        self.client.force_login(self.doctor)

    def write(self, path, payload, method="post"):
        return getattr(self.client, method)(path, data=json.dumps(payload), content_type="application/json")

    def booking(self):
        self.client.force_login(self.patient)
        result = self.write("/api/appointments", {"doctor": self.doctor.name, "service": self.service.name, "date": self.visit_date.isoformat(), "time": "09:00", "booking_token": "once", "appointment_sms_consent": True})
        self.assertIn(result.status_code, (200, 201), result.content)
        return Appointment.objects.get(pk=result.json()["appointment"]["id"])

    def record(self):
        return TreatmentRecord.objects.create(id="rec_sms", patient=self.profile, doctor=self.doctor, patient_name=self.profile.name, doctor_name=self.doctor.name, procedure=self.service.name, treatment_date=timezone.localdate(), amount_charged=1000, amount_paid=100, balance=900)

    def test_logs_group_technical_statuses_for_clinic_filters(self):
        groups = {
            "pending": ("queued", "processing", "submitted", "pending", "unknown"),
            "sent": ("sent",),
            "delivered": ("delivered",),
            "failed": ("failed", "refunded"),
            "not_sent": ("suppressed", "expired"),
        }
        for statuses in groups.values():
            for status in statuses:
                item = sms.enqueue("booking", self.profile, "status:" + status, sms.message_context(self.profile))
                SmsMessage.objects.filter(pk=item.pk).update(status=status)
        for group, statuses in groups.items():
            with self.subTest(group=group):
                response = self.client.get("/api/sms/logs", {"status": group})
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["total"], len(statuses))
                self.assertEqual({item["status"] for item in payload["messages"]}, set(statuses))
                self.assertEqual({item["display_status"] for item in payload["messages"]}, {group})

    def test_logs_group_filters_apply_before_pagination(self):
        for index in range(12):
            item = sms.enqueue("booking", self.profile, f"page:{index}", sms.message_context(self.profile))
            SmsMessage.objects.filter(pk=item.pk).update(status="submitted" if index % 2 else "queued")
        sms.enqueue("balance", self.profile, "other-rule", sms.message_context(self.profile))
        first = self.client.get("/api/sms/logs", {"status": "pending", "rule": "booking"}).json()
        second = self.client.get("/api/sms/logs", {"status": "pending", "rule": "booking", "page": 2}).json()
        self.assertEqual(first["total"], 12)
        self.assertEqual(second["total"], 12)
        self.assertEqual(len(first["messages"]), 10)
        self.assertEqual(len(second["messages"]), 2)
        self.assertFalse({item["id"] for item in first["messages"]} & {item["id"] for item in second["messages"]})

    def test_sent_messages_are_not_reported_as_delivered(self):
        item = sms.enqueue("booking", self.profile, "network-only", sms.message_context(self.profile))
        SmsMessage.objects.filter(pk=item.pk).update(status="sent")
        self.assertEqual(self.client.get("/api/sms/logs", {"status": "delivered"}).json()["total"], 0)
        self.assertEqual(self.client.get("/api/sms/logs").json()["messages"][0]["display_status"], "sent")

    def test_log_search_and_source_filters(self):
        for event, is_test in (("original", False), ("resend:original", False), ("test:sample", True)):
            sms.enqueue("booking", self.profile, event, sms.message_context(self.profile), is_test=is_test)
        for source in ("automated", "manual", "test"):
            response = self.client.get("/api/sms/logs", {"source": source, "q": self.profile.name}).json()
            self.assertEqual(response["total"], 1)
            self.assertEqual(response["messages"][0]["source"], source)
        self.assertEqual(self.client.get("/api/sms/logs", {"q": "+63 912 345 6789"}).json()["total"], 3)
        self.assertEqual(self.client.get("/api/sms/logs", {"q": "0912 345 6789"}).json()["total"], 3)
        self.assertEqual(self.client.get("/api/sms/logs", {"q": "No matching person"}).json()["total"], 0)

    def test_log_date_range_includes_entire_clinic_day(self):
        start = timezone.make_aware(dt.datetime(2026, 9, 21))
        for index, when in enumerate((start - dt.timedelta(seconds=1), start, start + dt.timedelta(hours=23, minutes=59, seconds=59), start + dt.timedelta(days=1))):
            item = sms.enqueue("booking", self.profile, f"date:{index}", sms.message_context(self.profile))
            SmsMessage.objects.filter(pk=item.pk).update(created_at=when)
        data = self.client.get("/api/sms/logs", {"date_from": "2026-09-21", "date_to": "2026-09-21"}).json()
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["stats"]["total"], 2)

    def test_log_metrics_use_real_states_and_future_schedule(self):
        for state in ("queued", "sent", "delivered", "failed", "refunded", "unknown"):
            item = sms.enqueue("booking", self.profile, "metric:" + state, sms.message_context(self.profile))
            SmsMessage.objects.filter(pk=item.pk).update(status=state, scheduled_for=timezone.now() + dt.timedelta(minutes=20))
        stats = self.client.get("/api/sms/logs").json()["stats"]
        self.assertEqual(stats, {"total": 6, "delivered": 1, "failed": 2, "scheduled": 1, "active_rules": 7, "total_rules": 7})
        filtered = self.client.get("/api/sms/logs", {"status": "failed"}).json()["stats"]
        self.assertEqual(filtered["total"], 2)
        self.assertEqual(filtered["delivered"], 0)
        self.assertEqual(filtered["scheduled"], 0)

    def test_log_page_size_and_page_clamping(self):
        for index in range(27):
            sms.enqueue("booking", self.profile, f"size:{index}", sms.message_context(self.profile))
        first = self.client.get("/api/sms/logs", {"page_size": 25}).json()
        last = self.client.get("/api/sms/logs", {"page_size": 25, "page": 99}).json()
        self.assertEqual(len(first["messages"]), 25)
        self.assertEqual(last["page"], 2)
        self.assertEqual(last["pages"], 2)
        self.assertEqual(len(last["messages"]), 2)

    def test_log_filters_reject_invalid_values(self):
        for values in ({"page": "bad"}, {"page_size": 1000}, {"source": "bad"}, {"rule": "bad"}, {"status": "bad"}, {"date_from": "bad"}, {"date_from": "2026-10-01", "date_to": "2026-09-01"}):
            with self.subTest(values=values):
                self.assertEqual(self.client.get("/api/sms/logs", values).status_code, 400)
        with timezone.override(dt.timezone(dt.timedelta(hours=8))):
            self.assertEqual(self.client.get("/api/sms/logs", {"date_from": "0001-01-01"}).status_code, 400)

    def test_log_details_include_only_recorded_provider_times(self):
        item = sms.enqueue("booking", self.profile, "detail", sms.message_context(self.profile))
        data = self.client.get("/api/sms/logs").json()["messages"][0]
        self.assertIsNone(data["submitted_at"])
        self.assertIsNone(data["checked_at"])
        self.assertEqual(data["scheduled_for"], item.scheduled_for.isoformat())
        self.assertFalse(data["can_resend"])
        self.assertEqual(data["source"], "automated")

    def failed_booking_message(self):
        appointment = self.booking()
        self.client.force_login(self.doctor)
        message = SmsMessage.objects.get(appointment=appointment)
        message.status = "failed"
        message.save(update_fields=["status"])
        return message

    def test_resend_preserves_original_and_is_idempotent(self):
        original = self.failed_booking_message()
        with patch("communications.sms_provider.send") as send:
            first = self.write("/api/sms/resend", {"id": original.pk})
            repeat = self.write("/api/sms/resend", {"id": original.pk})
            send.assert_not_called()
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(repeat.status_code, 200, repeat.content)
        self.assertEqual(first.json()["message"]["id"], repeat.json()["message"]["id"])
        self.assertEqual(first.json()["message"]["source"], "manual")
        self.assertEqual(first.json()["message"]["resend_of"], original.pk)
        self.assertEqual(SmsMessage.objects.count(), 2)
        original.refresh_from_db()
        self.assertEqual(original.status, "failed")
        log = self.client.get("/api/sms/logs", {"status": "failed"}).json()["messages"][0]
        self.assertFalse(log["can_resend"])
        self.assertEqual(log["resend_id"], first.json()["message"]["id"])
        with patch("communications.sms_provider.send", return_value=("resend-provider-id", "sent")) as send:
            sms.process_queue()
            self.assertEqual(send.call_count, 1)

    def test_resend_does_not_duplicate_uncertain_or_successful_messages(self):
        item = self.failed_booking_message()
        for state in ("unknown", "sent", "delivered", "pending"):
            SmsMessage.objects.filter(pk=item.pk).update(status=state)
            self.assertEqual(self.write("/api/sms/resend", {"id": item.pk}).status_code, 409)
        self.assertEqual(SmsMessage.objects.count(), 1)

    def test_resend_uses_current_appointment_and_template(self):
        original = self.failed_booking_message()
        updated_date = self.visit_date + dt.timedelta(days=2)
        Appointment.objects.filter(pk=original.appointment_id).update(appointment_date=updated_date, appointment_time=dt.time(14, 30))
        SmsRule.objects.filter(pk="booking").update(template="Hi {PatientName}. Visit: {AppointmentDate}, {Time}.")
        self.profile.mobile_number = "09123456780"
        self.profile.save()
        response = self.write("/api/sms/resend", {"id": original.pk})
        self.assertEqual(response.status_code, 201)
        message = response.json()["message"]
        self.assertEqual(message["phone"], "639123456780")
        self.assertIn(updated_date.strftime("%b %d, %Y"), message["body"])
        self.assertIn("02:30 PM", message["body"])
        original.refresh_from_db()
        self.assertIn("09:00 AM", original.body)

    def test_resend_respects_disabled_provider_rule_and_stale_appointment(self):
        item = self.failed_booking_message()
        with override_settings(SMS_ENABLED=False):
            self.assertEqual(self.write("/api/sms/resend", {"id": item.pk}).status_code, 409)
        SmsRule.objects.filter(pk="booking").update(enabled=False)
        self.assertEqual(self.write("/api/sms/resend", {"id": item.pk}).status_code, 409)
        SmsRule.objects.filter(pk="booking").update(enabled=True)
        Appointment.objects.filter(pk=item.appointment_id).update(status="cancelled")
        self.assertEqual(self.write("/api/sms/resend", {"id": item.pk}).status_code, 409)
        self.assertEqual(SmsMessage.objects.count(), 1)

    def test_resend_checks_expiry_balance_and_current_phone(self):
        self.record()
        item = sms.enqueue("balance", self.profile, "balance-retry", sms.message_context(self.profile))
        SmsMessage.objects.filter(pk=item.pk).update(status="failed", expires_at=timezone.now() - dt.timedelta(seconds=1))
        self.assertEqual(self.write("/api/sms/resend", {"id": item.pk}).status_code, 409)
        SmsMessage.objects.filter(pk=item.pk).update(expires_at=timezone.now() + dt.timedelta(hours=1))
        self.profile.mobile_number = "bad"
        self.profile.save()
        self.assertEqual(self.write("/api/sms/resend", {"id": item.pk}).status_code, 409)
        self.profile.mobile_number = "09123456789"
        self.profile.save()
        TreatmentRecord.objects.update(balance=0)
        self.assertEqual(self.write("/api/sms/resend", {"id": item.pk}).status_code, 409)

    def test_resend_requires_admin_and_csrf(self):
        item = self.failed_booking_message()
        self.assertEqual(self.write("/api/sms/resend", {"id": []}).status_code, 400)
        self.assertEqual(self.write("/api/sms/resend", {"id": "missing"}).status_code, 404)
        self.client.force_login(self.patient)
        self.assertEqual(self.write("/api/sms/resend", {"id": item.pk}).status_code, 403)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.doctor)
        self.assertEqual(secure.post("/api/sms/resend", data=json.dumps({"id": item.pk}), content_type="application/json").status_code, 403)

    def test_template_library_preserves_existing_rule_content(self):
        rule = SmsRule.objects.get(pk="booking")
        self.assertEqual(rule.active_template.body, rule.template)
        result = self.client.get("/api/sms/templates").json()
        self.assertEqual(len(result["templates"]), 7)
        self.assertEqual(sum(item["enabled"] for item in result["templates"]), 7)
        self.assertIn("appointment_reminder", {item["rule"] for item in result["templates"]})
        self.assertTrue(all(item["active"] and not item["can_delete"] for item in result["templates"]))
        sms.ensure_rules()
        self.assertEqual(SmsTemplate.objects.count(), 7)

    def test_template_library_handles_other_saved_rule_without_crashing(self):
        legacy_rule = SmsRule.objects.create(key="legacy_reminder", template="Legacy reminder")
        legacy_template = SmsTemplate.objects.create(
            id="smst_legacy_reminder", rule=legacy_rule,
            name="Legacy reminder", body="Legacy reminder",
        )
        legacy_rule.active_template = legacy_template
        legacy_rule.save(update_fields=["active_template"])

        response = self.client.get("/api/sms/templates")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.json()["templates"]), 8)
        self.assertEqual(
            next(item for item in response.json()["templates"] if item["id"] == legacy_template.pk)["trigger"],
            "Clinic message",
        )
        sms.enqueue("legacy_reminder", self.profile, "legacy:message", sms.message_context(self.profile))
        logs = self.client.get("/api/sms/logs")
        self.assertEqual(logs.status_code, 200, logs.content)
        self.assertEqual(logs.json()["messages"][0]["name"], "Legacy Reminder")
        self.assertTrue(SmsTemplate.objects.filter(pk=legacy_template.pk).exists())

    def create_template(self, **changes):
        payload = {"rule": "booking", "name": "Booking copy", "body": "Hello {PatientName}, {ClinicName} received your booking.", "delay_minutes": 15, "enabled": False, **changes}
        response = self.write("/api/sms/templates", payload)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["template"]

    def test_template_copy_is_inactive_until_selected(self):
        original = SmsRule.objects.get(pk="booking").active_template_id
        item = self.create_template()
        self.assertFalse(item["enabled"])
        self.assertEqual(SmsRule.objects.get(pk="booking").active_template_id, original)
        response = self.write("/api/sms/templates", {"id": item["id"], "enabled": True}, "patch")
        self.assertEqual(response.status_code, 200)
        rule = SmsRule.objects.get(pk="booking")
        self.assertEqual(rule.active_template_id, item["id"])
        self.assertEqual(rule.template, item["body"])
        self.assertEqual(rule.delay_minutes, 15)
        matching = [item for item in self.client.get("/api/sms/templates").json()["templates"] if item["rule"] == "booking"]
        self.assertEqual(sum(item["enabled"] for item in matching), 1)
        appointment = self.booking()
        self.assertEqual(SmsMessage.objects.filter(appointment=appointment).count(), 1)

    def test_template_edit_inactive_does_not_change_automation(self):
        before = SmsRule.objects.get(pk="booking").template
        item = self.create_template()
        body = "Welcome {PatientName} to {ClinicName}."
        response = self.write("/api/sms/templates", {"id": item["id"], "body": body, "name": "Updated copy"}, "patch")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SmsTemplate.objects.get(pk=item["id"]).body, body)
        self.assertEqual(SmsRule.objects.get(pk="booking").template, before)

    def test_inactive_template_can_be_deleted(self):
        item = self.create_template()
        response = self.write("/api/sms/templates", {"id": item["id"]}, "delete")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {"ok": True, "id": item["id"]})
        self.assertFalse(SmsTemplate.objects.filter(pk=item["id"]).exists())
        self.assertEqual(SmsTemplate.objects.count(), 7)

    def test_active_template_cannot_be_deleted_even_when_rule_is_off(self):
        rule = SmsRule.objects.get(pk="booking")
        response = self.write("/api/sms/templates", {"id": rule.active_template_id}, "delete")
        self.assertEqual(response.status_code, 409)
        SmsRule.objects.filter(pk="booking").update(enabled=False)
        response = self.write("/api/sms/templates", {"id": rule.active_template_id}, "delete")
        self.assertEqual(response.status_code, 409)
        self.assertTrue(SmsTemplate.objects.filter(pk=rule.active_template_id).exists())

    def test_replaced_template_can_be_deleted_without_changing_active_rule(self):
        original_id = SmsRule.objects.get(pk="booking").active_template_id
        replacement = self.create_template(enabled=True)
        response = self.write("/api/sms/templates", {"id": original_id}, "delete")
        self.assertEqual(response.status_code, 200, response.content)
        rule = SmsRule.objects.get(pk="booking")
        self.assertEqual(rule.active_template_id, replacement["id"])
        self.assertEqual(rule.template, replacement["body"])

    def test_template_delete_validation_access_and_csrf(self):
        item = self.create_template()
        self.assertEqual(self.write("/api/sms/templates", {"id": []}, "delete").status_code, 400)
        self.assertEqual(self.write("/api/sms/templates", {"id": "missing"}, "delete").status_code, 404)
        self.client.force_login(self.patient)
        self.assertEqual(self.write("/api/sms/templates", {"id": item["id"]}, "delete").status_code, 403)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.doctor)
        self.assertEqual(secure.delete("/api/sms/templates", data=json.dumps({"id": item["id"]}), content_type="application/json").status_code, 403)

    def test_template_off_suppresses_queue_and_rules_switch_stays_linked(self):
        appointment = self.booking()
        self.client.force_login(self.doctor)
        rule = SmsRule.objects.get(pk="booking")
        response = self.write("/api/sms/templates", {"id": rule.active_template_id, "enabled": False}, "patch")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SmsMessage.objects.get(appointment=appointment).status, "suppressed")
        self.assertFalse(SmsRule.objects.get(pk="booking").enabled)
        body = "Hi {PatientName}, your appointment request has been received."
        self.write("/api/sms/rules", {"key": "booking", "enabled": True, "template": body}, "patch")
        self.assertEqual(SmsTemplate.objects.get(pk=rule.active_template_id).body, body)
        self.assertTrue(next(item for item in self.client.get("/api/sms/templates").json()["templates"] if item["id"] == rule.active_template_id)["enabled"])

    def test_template_send_delay_is_used_without_sending_early(self):
        self.create_template(enabled=True, delay_minutes=30)
        now = timezone.now()
        with patch("communications.sms.timezone.now", return_value=now):
            item = sms.enqueue("booking", self.profile, "delayed-booking", sms.message_context(self.profile))
        self.assertEqual(item.scheduled_for, now + dt.timedelta(minutes=30))
        with patch("communications.sms_provider.send") as send:
            sms.process_queue()
            send.assert_not_called()
        with patch("communications.sms.timezone.now", return_value=now):
            test = sms.enqueue("booking", None, "immediate-test", sms.message_context(self.profile), phone="09123456789", is_test=True)
        self.assertEqual(test.scheduled_for, now)

    def test_template_validation_and_access(self):
        valid = {"rule": "booking", "name": "Copy", "body": "Hi {PatientName}."}
        for changes in ({"rule": []}, {"rule": "bad"}, {"body": "{Secret}"}, {"name": " "}, {"delay_minutes": True}, {"delay_minutes": -1}, {"delay_minutes": 999}, {"enabled": "yes"}):
            with self.subTest(changes=changes):
                self.assertEqual(self.write("/api/sms/templates", {**valid, **changes}).status_code, 400)
        self.assertEqual(self.write("/api/sms/templates", {"id": "missing"}, "patch").status_code, 404)
        self.client.force_login(self.patient)
        self.assertEqual(self.client.get("/api/sms/templates").status_code, 403)
        self.assertEqual(self.write("/api/sms/templates", valid).status_code, 403)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.doctor)
        self.assertEqual(secure.post("/api/sms/templates", data=json.dumps(valid), content_type="application/json").status_code, 403)

    def test_booking_replay_only_enqueues_once(self):
        item = self.booking()
        self.booking()
        self.assertEqual(SmsMessage.objects.filter(appointment=item, rule_id="booking").count(), 1)
        message = SmsMessage.objects.get(appointment=item)
        self.assertEqual(message.phone, "639123456789")
        self.assertIn("pending approval", message.body)

    def test_approval_cancellation_only_on_changes(self):
        item = self.booking()
        self.client.force_login(self.doctor)
        for status in ("approved", "approved", "cancelled", "cancelled"):
            self.assertEqual(self.write("/api/appointments", {"id": item.id, "status": status}, "patch").status_code, 200)
        self.assertEqual(SmsMessage.objects.filter(rule_id="approval").count(), 1)
        self.assertEqual(SmsMessage.objects.filter(rule_id="cancellation").count(), 1)
        self.assertTrue(SmsMessage.objects.filter(rule_id="booking", status="suppressed").exists())
        with patch("communications.sms_provider.send", return_value=("123", "submitted")) as send:
            sms.process_queue()
        self.assertEqual(send.call_count, 1)
        self.assertIn("cancelled", send.call_args.args[1])

    def test_walk_in_without_user(self):
        response = self.write("/api/appointments", {"name": "Walk In Patient", "phone": "09123456780", "doctor": self.doctor.name, "service": self.service.name, "date": self.visit_date.isoformat(), "time": "09:00"})
        self.assertEqual(response.status_code, 201, response.content)
        message = SmsMessage.objects.get(rule_id="walk_in")
        self.assertIsNone(message.patient.user_id)
        self.assertEqual(message.phone, "639123456780")

    def test_follow_up_rule(self):
        response = self.write("/api/appointments", {"patient_id": self.profile.id, "source": "follow_up", "doctor": self.doctor.name, "service": self.service.name, "date": self.visit_date.isoformat(), "time": "09:00", "notes": "Return visit"})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(SmsMessage.objects.get().rule_id, "next_visit")

    def test_approved_appointment_gets_one_before_visit_reminder(self):
        now = timezone.now().replace(second=0, microsecond=0)
        visit = timezone.localtime(now + dt.timedelta(hours=23))
        appointment = Appointment.objects.create(
            id="reminder_visit", patient=self.profile, doctor=self.doctor,
            patient_name=self.profile.name, doctor_name=self.doctor.name,
            service_name=self.service.name, appointment_date=visit.date(),
            appointment_time=visit.time(), status="approved", source="patient",
        )
        with patch(
            "communications.sms_provider.send", return_value=("456", "submitted")
        ) as send:
            sms.process_queue()
            sms.process_queue()
        reminders = SmsMessage.objects.filter(appointment=appointment, rule_id="appointment_reminder")
        self.assertEqual(reminders.count(), 1)
        self.assertEqual(reminders.get().status, "submitted")
        self.assertEqual(send.call_count, 1)

    def test_before_visit_reminder_respects_consent_and_schedule_changes(self):
        now = timezone.now().replace(second=0, microsecond=0)
        visit = timezone.localtime(now + dt.timedelta(hours=23))
        consented = Appointment.objects.create(
            id="reminder_consented", patient=self.profile, doctor=self.doctor,
            patient_name=self.profile.name, doctor_name=self.doctor.name,
            service_name=self.service.name, appointment_date=visit.date(),
            appointment_time=visit.time(), status="approved", source="patient",
        )
        no_consent = Appointment.objects.create(
            id="reminder_no_consent", patient=self.other_profile, doctor=self.doctor,
            patient_name=self.other_profile.name, doctor_name=self.doctor.name,
            service_name=self.service.name, appointment_date=visit.date(),
            appointment_time=visit.time(),
            status="approved", source="patient",
        )
        sms.queue_upcoming_patient_reminders(now)
        old_reminder = SmsMessage.objects.get(appointment=consented, rule_id="appointment_reminder")
        self.assertEqual(old_reminder.status, "queued")
        self.assertEqual(SmsMessage.objects.get(appointment=no_consent).status, "suppressed")

        rescheduled = timezone.localtime(now + dt.timedelta(hours=23, minutes=30))
        consented.appointment_date = rescheduled.date()
        consented.appointment_time = rescheduled.time()
        consented.save(update_fields=["appointment_date", "appointment_time", "updated_at"])
        with patch("communications.sms_provider.send") as send:
            sms.dispatch(old_reminder.pk, now)
        send.assert_not_called()
        old_reminder.refresh_from_db()
        self.assertEqual(old_reminder.status, "suppressed")
        sms.queue_upcoming_patient_reminders(now)
        self.assertEqual(SmsMessage.objects.filter(appointment=consented, rule_id="appointment_reminder").count(), 2)

    def test_cancelled_appointment_reminder_is_suppressed(self):
        now = timezone.now().replace(second=0, microsecond=0)
        visit = timezone.localtime(now + dt.timedelta(hours=23))
        appointment = Appointment.objects.create(
            id="reminder_cancelled", patient=self.profile, doctor=self.doctor,
            patient_name=self.profile.name, doctor_name=self.doctor.name,
            service_name=self.service.name, appointment_date=visit.date(),
            appointment_time=visit.time(), status="approved", source="patient",
        )
        sms.queue_upcoming_patient_reminders(now)
        appointment.status = "cancelled"
        appointment.save(update_fields=["status", "updated_at"])
        sms.appointment_event(appointment, "cancellation")
        self.assertEqual(SmsMessage.objects.get(appointment=appointment, rule_id="appointment_reminder").status, "suppressed")

    def test_bulk_cancellation_without_portal_notification(self):
        item = self.booking()
        self.client.force_login(self.doctor)
        response = self.write("/api/appointments", {"dates": self.visit_date.isoformat(), "notify_patients": False}, "delete")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SmsMessage.objects.get(appointment=item, rule_id="cancellation").status, "queued")

    def test_conflicting_pending_request_cancelled(self):
        first = self.booking()
        other = Appointment.objects.create(id="competing", patient=self.other_profile, doctor=self.doctor, patient_name=self.other_profile.name, doctor_name=self.doctor.name, service_name=self.service.name, appointment_date=self.visit_date, appointment_time=dt.time(9), status="pending", source="patient")
        self.client.force_login(self.doctor)
        self.assertEqual(self.write("/api/appointments", {"id": first.id, "status": "approved"}, "patch").status_code, 200)
        self.assertTrue(SmsMessage.objects.filter(appointment=other, rule_id="cancellation").exists())

    def test_transaction_rollback_removes_queue_entry(self):
        with self.assertRaises(ValueError):
            with transaction.atomic():
                sms.enqueue("balance", self.profile, "rollback", sms.message_context(self.profile))
                raise ValueError("rollback")
        self.assertFalse(SmsMessage.objects.filter(event_key="rollback").exists())

    def test_switches_persist_and_suppress_queued(self):
        item = self.booking()
        self.client.force_login(self.doctor)
        response = self.write("/api/sms/rules", {"key": "booking", "enabled": False, "template": "Hi {PatientName}, {ClinicName} received your request."}, "patch")
        self.assertEqual(response.status_code, 200)
        sms.ensure_rules()
        self.assertFalse(SmsRule.objects.get(pk="booking").enabled)
        self.assertEqual(SmsMessage.objects.get(appointment=item).status, "suppressed")
        self.write("/api/sms/rules", {"key": "all", "enabled": False}, "patch")
        self.assertFalse(SmsRule.objects.filter(enabled=True).exists())
        self.write("/api/sms/rules", {"key": "all", "enabled": True}, "patch")
        self.assertEqual(SmsRule.objects.filter(enabled=True).count(), 7)
        self.assertEqual(SmsMessage.objects.get(appointment=item).status, "suppressed")

    def test_disabled_rule_never_sends(self):
        SmsRule.objects.filter(pk="booking").update(enabled=False)
        self.booking()
        with patch("communications.sms_provider.send") as send:
            sms.process_queue()
            send.assert_not_called()
        self.assertEqual(SmsMessage.objects.get().status, "suppressed")

    def test_invalid_templates(self):
        for template in ("", "{Unknown}", "{PatientName.__class__}", "{PatientName!r}", "{Balance:1000000}", "TEST message"):
            self.assertEqual(self.write("/api/sms/rules", {"key": "booking", "template": template}, "patch").status_code, 400, template)

    def test_admin_only_and_csrf(self):
        self.client.force_login(self.patient)
        self.assertEqual(self.client.get("/api/sms").status_code, 403)
        self.assertEqual(self.client.get("/api/sms/logs").status_code, 403)
        self.assertEqual(self.write("/api/sms/rules", {"key": "all", "enabled": False}, "patch").status_code, 403)
        self.assertEqual(self.write("/api/sms/test", {}).status_code, 403)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.doctor)
        self.assertEqual(secure.patch("/api/sms/rules", data='{"key":"all","enabled":false}', content_type="application/json").status_code, 403)

    def test_unconfigured_never_sends(self):
        self.booking()
        with override_settings(SMS_ENABLED=False), patch("communications.sms_provider.send") as send:
            sms.process_queue()
            send.assert_not_called()
            self.client.force_login(self.doctor)
            self.assertEqual(self.write("/api/sms/test", {}).status_code, 409)
        self.assertEqual(SmsMessage.objects.get().status, "queued")

    def test_invalid_phone_does_not_block_booking(self):
        self.profile.mobile_number = "1234567"
        self.profile.save()
        self.booking()
        self.assertEqual(SmsMessage.objects.get().status, "failed")

    def test_current_template_phone_and_real_provider_status(self):
        self.booking()
        SmsRule.objects.filter(pk="booking").update(template="Hello {PatientName}. {ClinicName} is reviewing your request.")
        self.profile.mobile_number = "09123456780"
        self.profile.save()
        with patch("communications.sms_provider.send", return_value=("123", "submitted")) as send:
            sms.process_queue()
            sms.process_queue()
        self.assertEqual(send.call_count, 1)
        self.assertEqual(send.call_args.args[0], "639123456780")
        self.assertTrue(send.call_args.args[1].startswith("Hello"))
        message = SmsMessage.objects.get()
        self.assertEqual(message.status, "submitted")
        SmsMessage.objects.filter(pk=message.pk).update(checked_at=timezone.now() - dt.timedelta(minutes=2))
        with patch("communications.sms_provider.status", return_value=("123", "sent")):
            sms.process_queue()
        message.refresh_from_db()
        self.assertEqual(message.status, "sent")

    def test_timeout_never_retried(self):
        self.booking()
        with patch("communications.sms_provider.send", side_effect=sms_provider.SmsProviderError("Unknown", uncertain=True)) as send:
            sms.process_queue()
            sms.process_queue()
        self.assertEqual(send.call_count, 1)
        self.assertEqual(SmsMessage.objects.get().status, "unknown")

    def test_rate_limit_delayed_retry(self):
        self.booking()
        with patch("communications.sms_provider.send", side_effect=sms_provider.SmsProviderError("Rate limit", retryable=True)) as send:
            sms.process_queue()
            sms.process_queue()
        self.assertEqual(send.call_count, 1)
        self.assertEqual(SmsMessage.objects.get().status, "queued")
        self.assertGreater(SmsMessage.objects.get().scheduled_for, timezone.now())

    def test_stale_processing_needs_review(self):
        self.booking()
        SmsMessage.objects.update(status="processing", updated_at=timezone.now() - dt.timedelta(minutes=6))
        with patch("communications.sms_provider.send") as send:
            sms.process_queue()
            send.assert_not_called()
        self.assertEqual(SmsMessage.objects.get().status, "unknown")

    def test_former_provider_message_remains_unresolved_without_polling_or_resending(self):
        self.booking()
        queued = SmsMessage.objects.get(rule_id="booking")
        earlier = sms.enqueue("booking", self.profile, "former:earlier", sms.message_context(self.profile))
        SmsMessage.objects.filter(pk=earlier.pk).update(
            status="submitted", provider_id="former:earlier",
            checked_at=timezone.now() - dt.timedelta(minutes=2),
        )
        with patch("communications.sms.sms_provider.send", return_value=("456", "submitted")) as send, \
             patch("communications.sms.sms_provider.status") as status:
            self.assertEqual(sms.process_queue(), 1)
        send.assert_called_once()
        status.assert_not_called()
        queued.refresh_from_db()
        earlier.refresh_from_db()
        self.assertEqual((queued.status, queued.attempts, queued.provider_id), ("submitted", 1, "456"))
        self.assertEqual((earlier.status, earlier.provider_id), ("unknown", "former:earlier"))
        self.assertIn("original provider logs", earlier.error)

    def test_expiry(self):
        self.booking()
        SmsMessage.objects.update(expires_at=timezone.now() - dt.timedelta(seconds=1))
        with patch("communications.sms_provider.send") as send:
            sms.process_queue()
            send.assert_not_called()
        self.assertEqual(SmsMessage.objects.get().status, "expired")

    def test_past_appointment_notice_suppressed_before_send(self):
        item = self.booking()
        Appointment.objects.filter(pk=item.pk).update(appointment_date=timezone.localdate() - dt.timedelta(days=1))
        with patch("communications.sms_provider.send") as send:
            sms.process_queue()
            send.assert_not_called()
        self.assertEqual(SmsMessage.objects.get().status, "suppressed")

    def test_malformed_rule_key_is_validation_error(self):
        self.assertEqual(self.write("/api/sms/rules", {"key": [], "enabled": True}, "patch").status_code, 400)
        self.assertEqual(self.write("/api/sms/test", {"key": []}).status_code, 400)

    def test_dashboard_reports_real_counts_without_provider_secrets(self):
        self.booking()
        self.client.force_login(self.doctor)
        with patch(
            "communications.sms_views.sms_provider.account",
            return_value={"credit_balance": Decimal("1749"), "status": "Active"},
        ) as account:
            response = self.client.get("/api/sms")
            cached = self.client.get("/api/sms")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["stats"]["pending"], 1)
        self.assertEqual(data["stats"]["sent_today"], 0)
        self.assertIsNone(data["stats"]["success_rate"])
        self.assertEqual(data["provider"]["credit_balance"], 1749.0)
        self.assertEqual(data["provider"]["credit_status"], "Active")
        self.assertIsNotNone(data["provider"]["credit_checked_at"])
        self.assertEqual(cached.json()["provider"]["credit_balance"], 1749.0)
        account.assert_called_once()
        self.assertNotIn("fake-key", response.content.decode())

    def test_dashboard_credit_lookup_failure_and_missing_key(self):
        self.client.force_login(self.doctor)
        with patch(
            "communications.sms_views.sms_provider.account",
            side_effect=sms_provider.SmsProviderError("Semaphore account information is unavailable."),
        ):
            provider = self.client.get("/api/sms").json()["provider"]
        self.assertIsNone(provider["credit_balance"])
        self.assertEqual(provider["credit_status"], "unavailable")
        self.assertTrue(provider["credit_error"])

        cache.clear()
        with override_settings(SEMAPHORE_API_KEY=""), patch(
            "communications.sms_views.sms_provider.account"
        ) as account:
            provider = self.client.get("/api/sms").json()["provider"]
        self.assertIsNone(provider["credit_balance"])
        self.assertEqual(provider["credit_status"], "not_configured")
        account.assert_not_called()

    def test_weekly_balance_partial_and_full_payment(self):
        record = self.record()
        now = timezone.now()
        sms.sync_balance(self.profile, now)
        schedule = SmsBalanceSchedule.objects.get(patient=self.profile)
        self.assertEqual(schedule.next_due_at, now + dt.timedelta(days=7))
        sms.queue_due_balances(now + dt.timedelta(days=6))
        self.assertFalse(SmsMessage.objects.filter(rule_id="balance").exists())
        sms.queue_due_balances(now + dt.timedelta(days=7))
        sms.queue_due_balances(now + dt.timedelta(days=7))
        self.assertEqual(SmsMessage.objects.filter(rule_id="balance").count(), 1)
        record.balance = Decimal("400")
        record.amount_paid = Decimal("600")
        record.save()
        sms.sync_balance(self.profile, now + dt.timedelta(days=8))
        schedule.refresh_from_db()
        self.assertEqual(schedule.next_due_at, now + dt.timedelta(days=14))
        with patch("communications.sms_provider.send", return_value=("456", "sent")) as send:
            sms.process_queue()
        self.assertIn("400.00", send.call_args.args[1])
        sms.queue_due_balances(now + dt.timedelta(days=14))
        self.assertEqual(SmsMessage.objects.filter(rule_id="balance").count(), 2)
        record.balance = 0
        record.amount_paid = 1000
        record.save()
        sms.sync_balance(self.profile)
        self.assertFalse(SmsMessage.objects.filter(rule_id="balance", status="queued").exists())
        self.assertIsNone(SmsBalanceSchedule.objects.get(patient=self.profile).next_due_at)
        sms.queue_due_balances(now + dt.timedelta(days=21))
        self.assertEqual(SmsMessage.objects.filter(rule_id="balance").count(), 2)

    def test_balance_aggregate_and_send_time_recheck(self):
        self.record()
        TreatmentRecord.objects.create(id="rec_other", patient=self.profile, patient_name=self.profile.name, doctor_name=self.doctor.name, procedure=self.service.name, treatment_date=timezone.localdate(), amount_charged=200, balance=200)
        sms.enqueue("balance", self.profile, "aggregate", sms.message_context(self.profile))
        self.assertIn("1,100.00", SmsMessage.objects.get().body)
        TreatmentRecord.objects.update(balance=0)
        with patch("communications.sms_provider.send") as send:
            sms.process_queue()
            send.assert_not_called()

    def test_record_hook_and_deferred_next_visit(self):
        values = {"patient_id": self.profile.id, "procedure": self.service.name, "diagnosis": "Routine", "treatment_date": timezone.localdate().isoformat(), "amount_charged": 1000, "amount_paid": 100, "next_visit": self.visit_date.isoformat(), "schedule_follow_up": True}
        result = self.write("/api/records", values)
        self.assertEqual(result.status_code, 201, result.content)
        self.assertTrue(SmsBalanceSchedule.objects.filter(patient=self.profile, next_due_at__isnull=False).exists())
        self.assertFalse(SmsMessage.objects.exists())
        values.update({"id": result.json()["record"]["id"], "next_visit": (self.visit_date + dt.timedelta(days=1)).isoformat(), "schedule_follow_up": False})
        self.assertEqual(self.write("/api/records", values, "patch").status_code, 200)
        self.assertEqual(SmsMessage.objects.get().rule_id, "next_visit")
        self.assertEqual(self.write("/api/records", values, "patch").status_code, 200)
        self.assertEqual(SmsMessage.objects.count(), 1)

    def test_treatment_follow_up_booking_sends_one_appointment_sms(self):
        record_response = self.write("/api/records", {
            "patient_id": self.profile.id,
            "procedure": self.service.name,
            "diagnosis": "Follow-up needed",
            "treatment_date": timezone.localdate().isoformat(),
            "next_visit": self.visit_date.isoformat(),
            "schedule_follow_up": True,
        })
        self.assertEqual(record_response.status_code, 201, record_response.content)
        record = TreatmentRecord.objects.get(pk=record_response.json()["record"]["id"])
        self.assertEqual(record.patient_id, self.profile.id)
        self.assertEqual(record.next_visit, self.visit_date)
        self.assertFalse(SmsMessage.objects.exists())

        appointment_response = self.write("/api/appointments", {
            "patient_id": self.profile.id,
            "source": "follow_up",
            "doctor": self.doctor.name,
            "service": self.service.name,
            "date": self.visit_date.isoformat(),
            "time": "09:00",
            "notes": "Follow-up after treatment",
        })
        self.assertEqual(appointment_response.status_code, 201, appointment_response.content)
        appointment = Appointment.objects.get(pk=appointment_response.json()["appointment"]["id"])
        self.assertEqual(appointment.patient_id, record.patient_id)
        self.assertEqual(appointment.appointment_date, record.next_visit)
        self.assertEqual(appointment.status, "approved")
        self.assertEqual(appointment.source, "follow_up")

        messages = SmsMessage.objects.filter(rule_id="next_visit")
        self.assertEqual(SmsMessage.objects.count(), 1)
        self.assertEqual(messages.count(), 1)
        message = messages.get()
        self.assertEqual(message.appointment_id, appointment.id)
        self.assertIsNone(message.record_id)
        self.assertEqual(message.patient_id, self.profile.id)

    def test_test_sms_explicit_number_and_sample_data(self):
        response = self.write("/api/sms/test", {"key": "booking", "phone": "09123456789", "template": "Hi {PatientName}, {ClinicName}."})
        self.assertEqual(response.status_code, 201, response.content)
        item = SmsMessage.objects.get()
        self.assertTrue(item.is_test)
        self.assertIsNone(item.patient)
        self.assertIn("Sample Patient", item.body)

    def test_bulk_manual_sms_queues_personalized_messages_without_sending_in_request(self):
        self.other_profile.sms_consent = True
        self.other_profile.sms_consent_at = timezone.now()
        self.other_profile.save(update_fields=["sms_consent", "sms_consent_at"])
        payload = {
            "patient_ids": [self.profile.pk, self.other_profile.pk],
            "body": "Hi {PatientName}, this is {ClinicName}.",
            "request_id": str(uuid.uuid4()),
        }
        with patch("communications.sms_provider.send") as send:
            response = self.write("/api/sms/bulk", payload)
            send.assert_not_called()
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json(), {"queued_count": 2, "skipped": [], "already_queued": False})
        self.assertNotIn(self.profile.phone, response.content.decode())
        messages = list(SmsMessage.objects.filter(rule_id="manual").order_by("patient_id"))
        self.assertEqual(len(messages), 2)
        self.assertEqual({item.body for item in messages}, {
            f"Hi Patient One, this is {sms.message_context(self.profile)['ClinicName']}.",
            f"Hi Patient Two, this is {sms.message_context(self.other_profile)['ClinicName']}.",
        })
        self.assertEqual({item.status for item in messages}, {"queued"})
        logs = self.client.get("/api/sms/logs", {"source": "manual", "rule": "manual"}).json()
        self.assertEqual(logs["total"], 2)
        self.assertEqual({item["source"] for item in logs["messages"]}, {"manual"})
        self.assertEqual(self.client.get("/api/sms").json()["stats"]["active"], 7)
        self.assertEqual(len(self.client.get("/api/sms").json()["rules"]), 7)
        self.write("/api/sms/rules", {"key": "all", "enabled": False}, "patch")
        self.assertTrue(SmsRule.objects.get(pk="manual").enabled)
        self.assertEqual(set(SmsMessage.objects.values_list("status", flat=True)), {"queued"})

    def test_bulk_manual_sms_skips_inactive_consent_and_invalid_mobile(self):
        self.profile.mobile_number = "invalid"
        self.profile.save(update_fields=["mobile_number"])
        response = self.write("/api/sms/bulk", {
            "patient_ids": [self.profile.pk, self.other_profile.pk],
            "body": "Hello from {ClinicName}.",
            "request_id": str(uuid.uuid4()),
        })
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertEqual(data["queued_count"], 0)
        self.assertEqual([entry["patient_id"] for entry in data["skipped"]], [self.profile.pk, self.other_profile.pk])
        self.assertIn("valid Philippine mobile", data["skipped"][0]["reason"])
        self.assertEqual(data["skipped"][1]["reason"], "Patient SMS consent is not active.")
        self.assertEqual(set(SmsMessage.objects.values_list("status", flat=True)), {"failed", "suppressed"})

    def test_bulk_manual_sms_is_idempotent_and_rejects_changed_payload(self):
        payload = {
            "patient_ids": [self.profile.pk],
            "body": "Hello {PatientName}.",
            "request_id": str(uuid.uuid4()),
        }
        first = self.write("/api/sms/bulk", payload)
        again = self.write("/api/sms/bulk", payload)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json(), {"queued_count": 1, "skipped": [], "already_queued": True})
        self.assertEqual(SmsMessage.objects.count(), 1)
        self.assertEqual(self.write("/api/sms/bulk", {**payload, "body": "Different text."}).status_code, 409)
        self.assertEqual(self.write("/api/sms/bulk", {**payload, "patient_ids": [self.other_profile.pk]}).status_code, 409)
        self.assertEqual(SmsMessage.objects.count(), 1)

    def test_bulk_manual_sms_rechecks_consent_and_mobile_at_dispatch(self):
        response = self.write("/api/sms/bulk", {
            "patient_ids": [self.profile.pk], "body": "Hello {PatientName}.",
            "request_id": str(uuid.uuid4()),
        })
        self.assertEqual(response.status_code, 201)
        self.profile.mobile_number = "09123456780"
        self.profile.save(update_fields=["mobile_number"])
        with patch("communications.sms_provider.send", return_value=("bulk-provider-id", "sent")) as send:
            sms.process_queue()
        send.assert_called_once_with("639123456780", "Hello Patient One.")
        self.assertEqual(SmsMessage.objects.get().status, "sent")

        second = self.write("/api/sms/bulk", {
            "patient_ids": [self.profile.pk], "body": "A second clinic message.",
            "request_id": str(uuid.uuid4()),
        })
        self.assertEqual(second.status_code, 201)
        self.profile.sms_consent = False
        self.profile.save(update_fields=["sms_consent"])
        with patch("communications.sms_provider.send") as send:
            sms.process_queue()
            send.assert_not_called()
        self.assertEqual(SmsMessage.objects.get(body="A second clinic message.").status, "suppressed")

    def test_bulk_manual_sms_validates_selection_access_and_rate_limit(self):
        base = {"patient_ids": [self.profile.pk], "body": "Clinic notice.", "request_id": str(uuid.uuid4())}
        for invalid in (
            {**base, "patient_ids": [self.profile.pk, self.profile.pk]},
            {**base, "patient_ids": ["missing"]},
            {**base, "patient_ids": [self.profile.pk] * 51},
            {**base, "request_id": "not-a-uuid"},
        ):
            with self.subTest(invalid=invalid):
                self.assertEqual(self.write("/api/sms/bulk", invalid).status_code, 400)
        self.assertFalse(SmsMessage.objects.exists())
        self.client.force_login(self.patient)
        self.assertEqual(self.write("/api/sms/bulk", base).status_code, 403)
        self.client.force_login(self.doctor)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.doctor)
        self.assertEqual(secure.post("/api/sms/bulk", data=json.dumps(base), content_type="application/json").status_code, 403)
        with override_settings(SMS_ENABLED=False):
            self.assertEqual(self.write("/api/sms/bulk", base).status_code, 409)
        for _ in range(3):
            self.assertEqual(self.write("/api/sms/bulk", {**base, "request_id": str(uuid.uuid4())}).status_code, 201)
        self.assertEqual(self.write("/api/sms/bulk", {**base, "request_id": str(uuid.uuid4())}).status_code, 429)
        self.assertEqual(SmsMessage.objects.count(), 3)

    def test_manual_bulk_failure_can_be_resent_with_original_body(self):
        self.assertEqual(self.write("/api/sms/bulk", {
            "patient_ids": [self.profile.pk], "body": "Hi {PatientName}, from {ClinicName}.",
            "request_id": str(uuid.uuid4()),
        }).status_code, 201)
        original = SmsMessage.objects.get()
        SmsMessage.objects.filter(pk=original.pk).update(status="failed")
        response = self.write("/api/sms/resend", {"id": original.pk})
        self.assertEqual(response.status_code, 201, response.content)
        resent = SmsMessage.objects.get(event_key="resend:" + original.pk)
        self.assertEqual(resent.body, original.body)
        self.assertEqual(resent.rule_id, "manual")
        self.assertEqual(response.json()["message"]["source"], "manual")

    def test_worker_lease_blocks_overlapping_pass(self):
        self.booking()
        SmsWorker.objects.create(pk=1, lease_until=timezone.now() + dt.timedelta(minutes=2))
        with patch("communications.sms_provider.send") as send:
            self.assertEqual(sms.process_queue(), 0)
            send.assert_not_called()


@override_settings(SEMAPHORE_API_KEY="private-token", SEMAPHORE_SENDER_NAME="BORJA")
class SemaphoreTransportTests(TestCase):
    def test_semaphore_is_the_only_active_provider(self):
        with override_settings(SMS_ENABLED=True):
            self.assertEqual(sms_provider.name(), "Semaphore")
            self.assertTrue(sms_provider.ready())
            self.assertEqual(sms_provider.sender_name(), "BORJA")

    def test_normalize_numbers(self):
        for value in ("09123456789", "+63 912 345 6789", "9123456789", "639123456789"):
            self.assertEqual(sms_provider.normalize_phone(value), "639123456789")
        for value in ("", "0912345", "+12025550123", "09123456789,09999999999"):
            with self.assertRaises(ValueError):
                sms_provider.normalize_phone(value)

    def test_post_secret_in_body_and_network_status(self):
        response = BytesIO(b'[{"message_id":123,"status":"Sent"}]')
        with patch("communications.sms_provider.urlopen", return_value=response) as opener:
            self.assertEqual(sms_provider.send("09123456789", "Hello patient"), ("123", "sent"))
        req = opener.call_args.args[0]
        self.assertEqual(req.method, "POST")
        self.assertNotIn("private-token", req.full_url)
        self.assertIn(b"sendername=BORJA", req.data)

    def test_account_credit_balance_uses_semaphore_account_endpoint(self):
        response = BytesIO(
            b'{"account_id":42,"account_name":"BORJA","status":"Active","credit_balance":"1749.50"}'
        )
        with patch("communications.sms_provider.urlopen", return_value=response) as opener:
            account = sms_provider.account()
        self.assertEqual(account["credit_balance"], Decimal("1749.50"))
        self.assertEqual(account["status"], "Active")
        request = opener.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertIn("/api/v4/account?", request.full_url)

    def test_account_rejects_invalid_credit_balance(self):
        for body in (b'{}', b'{"credit_balance":"not-a-number"}', b'{"credit_balance":-1}'):
            with self.subTest(body=body), patch(
                "communications.sms_provider.urlopen", return_value=BytesIO(body)
            ):
                with self.assertRaises(sms_provider.SmsProviderError):
                    sms_provider.account()

    def test_status_rejects_non_semaphore_id_without_network(self):
        with patch("communications.sms_provider.urlopen") as opener:
            with self.assertRaises(sms_provider.SmsProviderError):
                sms_provider.status("former:abc")
        opener.assert_not_called()

    def test_errors_do_not_expose_secrets(self):
        with patch("communications.sms_provider.urlopen", side_effect=HTTPError("https://example/?apikey=private-token", 401, "private-token", {}, None)):
            with self.assertRaises(sms_provider.SmsProviderError) as caught:
                sms_provider.send("09123456789", "Hello")
        self.assertNotIn("private-token", str(caught.exception))
        self.assertFalse(caught.exception.uncertain)
