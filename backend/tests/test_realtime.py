import datetime as dt
import json

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.test import Client, TransactionTestCase

from accounts.models import PatientProfile, User
from clinic.models import Service
from dental_backend.asgi import application
from dental_backend.realtime import CHANGE_EVENT, publish_dashboard_change
from scheduling.models import Appointment, AvailabilitySlot


class DashboardRealtimeTests(TransactionTestCase):
    def setUp(self):
        self.doctor = User.objects.create_user(
            email="realtime-doctor@example.com", password="TestDoctor123!",
            name="Dr. Realtime", role="doctor",
        )
        self.patient = User.objects.create_user(
            email="realtime-patient@example.com", password="TestPatient123!",
            name="Patient Realtime", phone="09123456789", role="patient",
        )
        PatientProfile.objects.create(
            id=self.patient.id, user=self.patient, first_name="Patient",
            last_name="Realtime", email=self.patient.email,
            mobile_number=self.patient.phone,
        )
        self.service = Service.objects.create(
            id="svc_realtime", name="Realtime Cleaning",
        )
        self.visit_date = dt.date.today() + dt.timedelta(days=7)
        AvailabilitySlot.objects.create(
            id="slot_realtime", doctor=self.doctor, doctor_name=self.doctor.name,
            date=self.visit_date, time=dt.time(9, 0),
        )
        self.doctor_client = Client()
        self.doctor_client.force_login(self.doctor)
        self.patient_client = Client()
        self.patient_client.force_login(self.patient)

    def communicator(self, client=None, origin="https://borjadentalclinic.up.railway.app"):
        headers = [(b"origin", origin.encode()), (b"host", b"localhost:8000")]
        if client:
            cookie = client.cookies[settings.SESSION_COOKIE_NAME].value
            headers.append((b"cookie", f"{settings.SESSION_COOKIE_NAME}={cookie}".encode()))
        return WebsocketCommunicator(application, "/ws/admin-updates/", headers=headers)

    def book(self):
        return self.patient_client.post(
            "/api/appointments",
            data=json.dumps({
                "doctor": self.doctor.name,
                "service": self.service.name,
                "date": self.visit_date.isoformat(),
                "time": "09:00",
            }),
            content_type="application/json",
        )

    async def test_patient_booking_updates_doctor_socket_from_database(self):
        socket = self.communicator(self.doctor_client)
        connected, _ = await socket.connect()
        self.assertTrue(connected)
        try:
            response = await sync_to_async(self.book)()
            self.assertEqual(response.status_code, 201)
            self.assertEqual(await socket.receive_json_from(timeout=3), CHANGE_EVENT)

            listed = await sync_to_async(self.doctor_client.get)("/api/appointments")
            self.assertEqual(
                listed.json()["appointments"][0]["id"],
                response.json()["appointment"]["id"],
            )

            cancelled = await sync_to_async(self.patient_client.patch)(
                "/api/appointments",
                data=json.dumps({"id": response.json()["appointment"]["id"], "status": "cancelled"}),
                content_type="application/json",
            )
            self.assertEqual(cancelled.status_code, 200)
            self.assertEqual(await socket.receive_json_from(timeout=3), CHANGE_EVENT)

            changed_profile = await sync_to_async(self.patient_client.patch)(
                "/api/profile",
                data=json.dumps({
                    "name": "Patient Updated", "email": self.patient.email,
                    "phone": self.patient.phone,
                }),
                content_type="application/json",
            )
            self.assertEqual(changed_profile.status_code, 200)
            self.assertEqual(await socket.receive_json_from(timeout=3), CHANGE_EVENT)

            feedback = await sync_to_async(self.patient_client.post)(
                "/api/feedback",
                data=json.dumps({"rating": 5, "message": "Helpful visit and kind staff."}),
                content_type="application/json",
            )
            self.assertEqual(feedback.status_code, 201)
            self.assertEqual(await socket.receive_json_from(timeout=3), CHANGE_EVENT)

            message = await sync_to_async(self.patient_client.post)(
                "/api/messages",
                data=json.dumps({"recipient_id": self.doctor.id, "body": "Can I ask about my next visit?"}),
                content_type="application/json",
            )
            self.assertEqual(message.status_code, 201)
            self.assertEqual(await socket.receive_json_from(timeout=3), CHANGE_EVENT)

            listed = await sync_to_async(self.doctor_client.get)("/api/appointments")
            self.assertEqual(listed.json()["appointments"][0]["patient_name"], "Patient Updated")
            self.assertEqual(listed.json()["appointments"][0]["status"], "cancelled")
        finally:
            await socket.disconnect()

    async def test_patient_anonymous_and_untrusted_origins_are_rejected(self):
        for socket in (
            self.communicator(self.patient_client),
            self.communicator(),
            self.communicator(self.doctor_client, origin="https://untrusted.example"),
        ):
            connected, _ = await socket.connect()
            self.assertFalse(connected)

    async def test_configured_frontend_origins_are_accepted(self):
        for origin in (
            "https://borjadentalclinic.up.railway.app",
            "https://borjadentalclinic.site",
            "https://www.borjadentalclinic.site",
        ):
            socket = self.communicator(self.doctor_client, origin=origin)
            connected, _ = await socket.connect()
            self.assertTrue(connected)
            await socket.disconnect()

    async def test_logged_out_session_stops_receiving_updates(self):
        socket = self.communicator(self.doctor_client)
        connected, _ = await socket.connect()
        self.assertTrue(connected)
        await sync_to_async(self.doctor_client.logout)()
        await sync_to_async(publish_dashboard_change)()
        response = await socket.receive_output(timeout=3)
        self.assertEqual(response["type"], "websocket.close")
        self.assertEqual(response["code"], 4403)

    async def test_disabled_doctor_stops_receiving_updates(self):
        socket = self.communicator(self.doctor_client)
        connected, _ = await socket.connect()
        self.assertTrue(connected)
        await sync_to_async(User.objects.filter(pk=self.doctor.pk).update)(is_active=False)
        await sync_to_async(publish_dashboard_change)()
        response = await socket.receive_output(timeout=3)
        self.assertEqual(response["type"], "websocket.close")
        self.assertEqual(response["code"], 4403)

    async def test_clinic_patient_edit_refreshes_appointment_contact_details(self):
        manual = await sync_to_async(PatientProfile.objects.create)(
            id="pat_manual_realtime", first_name="Old", last_name="Name",
            email="old-realtime@example.com", mobile_number="09123456700",
        )
        await sync_to_async(Appointment.objects.create)(
            id="apt_manual_realtime", patient=manual, doctor=self.doctor,
            doctor_name=self.doctor.name, patient_name=manual.name,
            patient_email=manual.email, patient_phone=manual.phone,
            service_name=self.service.name, appointment_date=self.visit_date,
            appointment_time=dt.time(10, 0), status="approved", source="manual",
        )
        socket = self.communicator(self.doctor_client)
        connected, _ = await socket.connect()
        self.assertTrue(connected)
        try:
            updated = await sync_to_async(self.doctor_client.patch)(
                "/api/patients",
                data=json.dumps({
                    "id": manual.id, "first_name": "New", "last_name": "Name",
                    "email": "new-realtime@example.com",
                    "phone_number": "09123456701", "mobile_number": "09123456701",
                    "birthdate": "1990-01-01", "sex": "female",
                    "address": "123 Main Street", "nationality": "Filipino",
                    "occupation": "Teacher",
                }),
                content_type="application/json",
            )
            self.assertEqual(updated.status_code, 200)
            self.assertEqual(await socket.receive_json_from(timeout=3), CHANGE_EVENT)
            listed = await sync_to_async(self.doctor_client.get)("/api/appointments")
            item = next(item for item in listed.json()["appointments"] if item["id"] == "apt_manual_realtime")
            self.assertEqual(item["patient_name"], "New Name")
            self.assertEqual(item["patient_email"], "new-realtime@example.com")
            self.assertEqual(item["patient_phone"], "09123456701")
        finally:
            await socket.disconnect()
