import datetime as dt
import json
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from accounts.models import PatientProfile, User
from clinic.models import Service
from communications import sms
from communications.models import DoctorNotificationPreference, Notification, SmsBalanceSchedule, SmsMessage, SmsRule
from communications.services import notify_due_next_visits, notify_upcoming_appointments
from scheduling.models import Appointment, AvailabilitySlot


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"], SMS_ENABLED=False)
class DoctorNotificationPreferenceTests(TestCase):
    def setUp(self):
        self.doctor = User.objects.create_user(
            email="dentist@example.com", password="Strong123!", name="Dr. Maria Santos", role="doctor"
        )
        self.patient_user = User.objects.create_user(
            email="patient@example.com", password="Strong123!", name="Patient One", phone="09123456789", role="patient"
        )
        self.patient = PatientProfile.objects.create(
            id="pat_notify", user=self.patient_user, first_name="Patient", last_name="One",
            email=self.patient_user.email, mobile_number=self.patient_user.phone,
        )
        self.service = Service.objects.create(id="svc_notify", name="Cleaning", description="Routine cleaning")
        self.day = timezone.localdate() + dt.timedelta(days=7)
        self.slot(self.day)
        self.client = Client()
        sms.ensure_rules()

    def slot(self, day, hour=9):
        return AvailabilitySlot.objects.create(
            id=f"avail_{day.isoformat()}_{hour}", doctor=self.doctor,
            doctor_name=self.doctor.name, date=day, time=dt.time(hour, 0),
        )

    def request(self, path, values, method="post"):
        return getattr(self.client, method)(path, data=json.dumps(values), content_type="application/json")

    def set_preferences(self, **values):
        self.client.force_login(self.doctor)
        response = self.request("/api/notification-preferences", {"preferences": values}, "patch")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["preferences"]

    def test_preferences_persist_and_do_not_change_patient_sms_rules(self):
        self.client.force_login(self.doctor)
        initial = self.client.get("/api/notification-preferences")
        self.assertEqual(initial.status_code, 200)
        self.assertTrue(all(initial.json()["preferences"].values()))
        self.set_preferences(new_appointment_booking=False, sms_delivery_failure=False)
        self.assertFalse(self.client.get("/api/notification-preferences").json()["preferences"]["new_appointment_booking"])
        self.assertFalse(DoctorNotificationPreference.objects.get(user=self.doctor).sms_delivery_failure)
        self.assertTrue(SmsRule.objects.get(pk="booking").enabled)
        self.assertEqual(
            self.request("/api/notification-preferences", {"preferences": {"new_appointment_booking": "false"}}, "patch").status_code,
            400,
        )
        self.client.force_login(self.patient_user)
        self.assertEqual(self.client.get("/api/notification-preferences").status_code, 403)
        self.assertEqual(
            self.request("/api/notification-preferences", {"preferences": {"new_appointment_booking": True}}, "patch").status_code,
            403,
        )

    def test_booking_toggle_does_not_suppress_patient_notice_or_sms(self):
        self.set_preferences(new_appointment_booking=False)
        self.client.force_login(self.patient_user)
        response = self.request("/api/appointments", {
            "doctor": self.doctor.name, "service": self.service.name,
            "date": self.day.isoformat(), "time": "09:00",
            "appointment_sms_consent": True,
        })
        self.assertEqual(response.status_code, 201, response.content)
        self.assertFalse(Notification.objects.filter(recipient=self.doctor, title="New appointment request").exists())
        self.assertTrue(Notification.objects.filter(recipient=self.patient_user, title="Appointment request submitted").exists())
        self.assertTrue(SmsMessage.objects.filter(rule_id="booking").exists())

        next_day = self.day + dt.timedelta(days=1)
        self.slot(next_day)
        self.set_preferences(new_appointment_booking=True)
        self.client.force_login(self.patient_user)
        response = self.request("/api/appointments", {
            "doctor": self.doctor.name, "service": self.service.name,
            "date": next_day.isoformat(), "time": "09:00",
            "appointment_sms_consent": True,
        })
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Notification.objects.filter(recipient=self.doctor, title="New appointment request").count(), 1)

    def test_walk_in_and_status_toggles_control_real_appointment_events(self):
        self.set_preferences(new_walk_in_appointment=False, appointment_cancellation=False, appointment_confirmed=False)
        response = self.request("/api/appointments", {
            "doctor": self.doctor.name, "service": self.service.name, "patient_id": self.patient.id,
            "date": self.day.isoformat(), "time": "09:00",
        })
        self.assertEqual(response.status_code, 201, response.content)
        appointment_id = response.json()["appointment"]["id"]
        self.assertFalse(Notification.objects.filter(recipient=self.doctor, title="New walk-in appointment").exists())
        response = self.request("/api/appointments", {"id": appointment_id, "status": "cancelled"}, "patch")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(Notification.objects.filter(recipient=self.doctor, title="Appointment cancelled").exists())
        self.assertTrue(Notification.objects.filter(recipient=self.patient_user, title="Appointment cancelled").exists())

        self.set_preferences(new_walk_in_appointment=True, appointment_cancellation=True)
        second_day = self.day + dt.timedelta(days=1)
        self.slot(second_day)
        response = self.request("/api/appointments", {
            "doctor": self.doctor.name, "service": self.service.name, "patient_id": self.patient.id,
            "date": second_day.isoformat(), "time": "09:00",
        })
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Notification.objects.filter(recipient=self.doctor, title="New walk-in appointment").count(), 1)
        response = self.request("/api/appointments", {"id": response.json()["appointment"]["id"], "status": "cancelled"}, "patch")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Notification.objects.filter(recipient=self.doctor, title="Appointment cancelled").count(), 1)

    def test_accepted_appointment_uses_confirmation_preference_once(self):
        self.set_preferences(appointment_confirmed=False)
        self.client.force_login(self.patient_user)
        response = self.request("/api/appointments", {
            "doctor": self.doctor.name, "service": self.service.name,
            "date": self.day.isoformat(), "time": "09:00",
            "appointment_sms_consent": True,
        })
        self.assertEqual(response.status_code, 201, response.content)
        appointment_id = response.json()["appointment"]["id"]
        self.client.force_login(self.doctor)
        response = self.request("/api/appointments", {"id": appointment_id, "status": "approved"}, "patch")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(Notification.objects.filter(recipient=self.doctor, title="Appointment accepted").exists())
        self.assertTrue(Notification.objects.filter(recipient=self.patient_user, title="Appointment accepted").exists())

        self.set_preferences(appointment_confirmed=True)
        next_day = self.day + dt.timedelta(days=1)
        self.slot(next_day)
        self.client.force_login(self.patient_user)
        response = self.request("/api/appointments", {
            "doctor": self.doctor.name, "service": self.service.name,
            "date": next_day.isoformat(), "time": "09:00",
            "appointment_sms_consent": True,
        })
        self.assertEqual(response.status_code, 201, response.content)
        self.client.force_login(self.doctor)
        response = self.request("/api/appointments", {"id": response.json()["appointment"]["id"], "status": "approved"}, "patch")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Notification.objects.filter(recipient=self.doctor, title="Appointment accepted").count(), 1)

    def test_next_visit_and_balance_events_are_separate_from_sms_rules(self):
        self.set_preferences(next_visit=False, payment_balance_reminder=False)
        response = self.request("/api/records", {
            "patient_id": self.patient.id, "procedure": self.service.name, "diagnosis": "Plaque",
            "treatment_date": timezone.localdate().isoformat(), "next_visit": self.day.isoformat(),
            "amount_charged": "1000", "amount_paid": "100",
        })
        self.assertEqual(response.status_code, 201, response.content)
        self.assertFalse(Notification.objects.filter(recipient=self.doctor, notification_type="next_visit").exists())
        self.assertTrue(SmsMessage.objects.filter(rule_id="next_visit").exists())
        first_due = timezone.make_aware(
            dt.datetime.combine(self.day, dt.time(9, 0)), timezone.get_current_timezone()
        )
        self.assertEqual(notify_due_next_visits(first_due), 0)
        schedule = SmsBalanceSchedule.objects.get(patient=self.patient)
        schedule.next_due_at = timezone.now() - dt.timedelta(minutes=1)
        schedule.save(update_fields=["next_due_at"])
        sms.queue_due_balances(timezone.now())
        self.assertFalse(Notification.objects.filter(recipient=self.doctor, notification_type="payment_balance_reminder").exists())
        self.assertTrue(SmsMessage.objects.filter(rule_id="balance").exists())

        self.set_preferences(next_visit=True, payment_balance_reminder=True)
        response = self.request("/api/records", {
            "id": response.json()["record"]["id"], "patient_id": self.patient.id,
            "procedure": self.service.name, "diagnosis": "Plaque",
            "treatment_date": timezone.localdate().isoformat(),
            "next_visit": (self.day + dt.timedelta(days=1)).isoformat(),
            "amount_charged": "1000", "amount_paid": "100",
        }, "patch")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(Notification.objects.filter(recipient=self.doctor, notification_type="next_visit").exists())
        sms_count = SmsMessage.objects.count()
        new_due = first_due + dt.timedelta(days=1)
        self.assertEqual(notify_due_next_visits(first_due), 0)
        self.assertEqual(notify_due_next_visits(new_due), 1)
        self.assertEqual(notify_due_next_visits(new_due), 0)
        self.assertEqual(notify_due_next_visits(new_due + dt.timedelta(days=1)), 0)
        self.assertEqual(Notification.objects.filter(recipient=self.doctor, notification_type="next_visit").count(), 1)
        self.assertEqual(SmsMessage.objects.count(), sms_count)
        schedule.refresh_from_db()
        schedule.next_due_at = timezone.now() - dt.timedelta(minutes=1)
        schedule.save(update_fields=["next_due_at"])
        sms.queue_due_balances(timezone.now())
        self.assertEqual(Notification.objects.filter(recipient=self.doctor, notification_type="payment_balance_reminder").count(), 1)

    @patch("communications.sms.sms_provider.send", side_effect=[("123", "failed"), ("124", "failed")])
    def test_terminal_sms_failure_notifies_once_when_enabled(self, _send):
        self.set_preferences(sms_delivery_failure=False)
        item = sms.enqueue("booking", self.patient, "failure:test:one", sms.message_context(self.patient), is_test=True)
        sms.dispatch(item.id, timezone.now())
        self.assertFalse(Notification.objects.filter(recipient=self.doctor, notification_type="sms_delivery_failure").exists())

        self.set_preferences(sms_delivery_failure=True)
        second = sms.enqueue("booking", self.patient, "failure:test:two", sms.message_context(self.patient), is_test=True)
        sms.dispatch(second.id, timezone.now())
        self.assertEqual(Notification.objects.filter(recipient=self.doctor, notification_type="sms_delivery_failure").count(), 1)

    @patch("communications.sms.sms_provider.status", return_value=("125", "refunded"))
    @patch("communications.sms.sms_provider.ready", return_value=True)
    def test_provider_status_failure_creates_one_dashboard_notice(self, _ready, _status):
        item = sms.enqueue("booking", self.patient, "failure:provider", sms.message_context(self.patient), is_test=True)
        SmsMessage.objects.filter(pk=item.pk).update(
            status="submitted", provider_id="125", checked_at=timezone.now() - dt.timedelta(minutes=2)
        )
        sms.process_queue()
        self.assertEqual(Notification.objects.filter(recipient=self.doctor, notification_type="sms_delivery_failure").count(), 1)
        sms.process_queue()
        self.assertEqual(Notification.objects.filter(recipient=self.doctor, notification_type="sms_delivery_failure").count(), 1)

    def test_upcoming_reminder_is_due_once_per_approved_slot_and_is_not_sms(self):
        now = timezone.localtime(timezone.now()).replace(hour=9, minute=0, second=0, microsecond=0)
        appointment = Appointment.objects.create(
            id="appt_upcoming", patient=self.patient, doctor=self.doctor,
            patient_name=self.patient.name, doctor_name=self.doctor.name,
            service_name=self.service.name, appointment_date=now.date() + dt.timedelta(days=1),
            appointment_time=dt.time(9, 0), status="approved", source="manual",
        )
        sms_count = SmsMessage.objects.count()
        self.assertEqual(notify_upcoming_appointments(now - dt.timedelta(seconds=1)), 0)
        self.assertEqual(notify_upcoming_appointments(now), 1)
        self.assertEqual(notify_upcoming_appointments(now + dt.timedelta(minutes=1)), 0)
        notice = Notification.objects.get(recipient=self.doctor, notification_type="upcoming_appointment_reminder")
        self.assertEqual(notice.entity_id, appointment.pk)
        self.assertIn(self.patient.name, notice.message)
        self.assertEqual(SmsMessage.objects.count(), sms_count)

        appointment.status = "cancelled"
        appointment.save(update_fields=["status"])
        self.assertEqual(notify_upcoming_appointments(now), 0)

    def test_upcoming_reminder_preference_and_worker_without_sms_gateway(self):
        now = timezone.localtime(timezone.now()).replace(hour=9, minute=0, second=0, microsecond=0)
        Appointment.objects.create(
            id="appt_upcoming_worker", patient=self.patient, doctor=self.doctor,
            patient_name=self.patient.name, doctor_name=self.doctor.name,
            service_name=self.service.name, appointment_date=now.date() + dt.timedelta(days=1),
            appointment_time=dt.time(9, 0), status="approved", source="manual",
        )
        self.set_preferences(upcoming_appointment_reminder=False)
        self.assertEqual(notify_upcoming_appointments(now), 0)
        self.set_preferences(upcoming_appointment_reminder=True)
        with patch("communications.sms.timezone.now", return_value=now):
            self.assertEqual(sms.process_queue(), 0)
            self.assertEqual(sms.process_queue(), 0)
        self.assertEqual(
            Notification.objects.filter(recipient=self.doctor, notification_type="upcoming_appointment_reminder").count(),
            1,
        )
