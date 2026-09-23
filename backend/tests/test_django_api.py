import datetime as dt

from django.core.cache import cache
from django.test import Client, TestCase

from accounts.models import PatientProfile, User
from clinic.models import Service
from communications.models import Notification
from records.models import TreatmentRecord
from scheduling.models import Appointment, AvailabilitySlot


class DentalApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.doctor = User.objects.create_user(
            id="usr_doctor_test",
            email="doctor@example.com",
            password="Doctor123!",
            name="Dr. Maria Santos",
            role="doctor",
            is_staff=True,
        )
        self.patient = User.objects.create_user(
            id="usr_patient_one",
            email="patient1@example.com",
            password="Patient123!",
            name="Patient One",
            phone="09123456789",
            role="patient",
        )
        self.profile = PatientProfile.objects.create(
            id=self.patient.id,
            user=self.patient,
            first_name="Patient",
            last_name="One",
            email=self.patient.email,
            mobile_number=self.patient.phone,
        )
        self.other_patient = User.objects.create_user(
            id="usr_patient_two",
            email="patient2@example.com",
            password="Patient123!",
            name="Patient Two",
            phone="09987654321",
            role="patient",
        )
        self.other_profile = PatientProfile.objects.create(
            id=self.other_patient.id,
            user=self.other_patient,
            first_name="Patient",
            last_name="Two",
            email=self.other_patient.email,
            mobile_number=self.other_patient.phone,
        )
        self.service = Service.objects.create(
            id="svc_test_cleaning",
            name="Oral Prophylaxis",
            description="Routine cleaning and plaque removal.",
        )
        self.visit_date = dt.date.today() + dt.timedelta(days=7)
        self.slot = AvailabilitySlot.objects.create(
            id="avail_test_0900",
            doctor=self.doctor,
            doctor_name=self.doctor.name,
            date=self.visit_date,
            time=dt.time(9, 0),
        )

    def csrf_client(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get("/api/session")
        self.assertEqual(response.status_code, 200)
        token = response.json()["csrf_token"]
        return client, token

    def post_json(self, client, token, path, data):
        return client.post(
            path,
            data=data,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

    def patch_json(self, client, token, path, data):
        return client.patch(
            path,
            data=data,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

    def test_session_csrf_login_wrong_password_and_logout(self):
        client, token = self.csrf_client()
        wrong = self.post_json(
            client,
            token,
            "/api/login",
            {"email": self.patient.email, "password": "wrong"},
        )
        self.assertEqual(wrong.status_code, 401)

        response = self.post_json(
            client,
            token,
            "/api/login",
            {"email": self.patient.email, "password": "Patient123!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["role"], "patient")
        new_token = response.json()["csrf_token"]
        self.assertEqual(client.get("/api/session").json()["user"]["id"], self.patient.id)
        logout = self.post_json(client, new_token, "/api/logout", {})
        self.assertEqual(logout.status_code, 200)
        self.assertIsNone(client.get("/api/session").json()["user"])

    def test_patient_registration_creates_profile_and_session(self):
        client, token = self.csrf_client()
        response = self.post_json(
            client,
            token,
            "/api/register",
            {
                "name": "New Patient",
                "email": "new.patient@example.com",
                "phone": "09112223333",
                "password": "NewPatient123!",
                "role": "patient",
            },
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="new.patient@example.com")
        self.assertTrue(user.check_password("NewPatient123!"))
        self.assertEqual(user.patient_profile.id, user.id)
        self.assertEqual(client.get("/api/session").json()["user"]["id"], user.id)

    def test_doctor_patient_create_and_update_sex(self):
        client, token = self.csrf_client()
        client.force_login(self.doctor)
        payload = {
            "first_name": "Alex",
            "last_name": "Rivera",
            "email": "alex.rivera@example.com",
            "mobile_number": "09123456780",
            "birthdate": "1995-04-12",
            "sex": "female",
            "address": "123 Main Street",
            "nationality": "Filipino",
            "occupation": "Teacher",
        }

        created = self.post_json(client, token, "/api/patients", payload)
        self.assertEqual(created.status_code, 201)
        patient_id = created.json()["patient"]["id"]
        self.assertEqual(created.json()["patient"]["sex"], "female")
        self.assertEqual(PatientProfile.objects.get(id=patient_id).sex, "female")

        updated = self.patch_json(
            client, token, "/api/patients", {**payload, "id": patient_id, "sex": "male"}
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["patient"]["sex"], "male")
        self.assertEqual(PatientProfile.objects.get(id=patient_id).sex, "male")

    def test_doctor_patient_create_requires_sex(self):
        client, token = self.csrf_client()
        client.force_login(self.doctor)
        response = self.post_json(
            client,
            token,
            "/api/patients",
            {
                "first_name": "Alex",
                "last_name": "Rivera",
                "email": "alex.rivera@example.com",
                "mobile_number": "09123456780",
                "birthdate": "1995-04-12",
                "address": "123 Main Street",
                "nationality": "Filipino",
                "occupation": "Teacher",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("sex", response.json()["error"].lower())
        self.assertFalse(PatientProfile.objects.filter(email="alex.rivera@example.com").exists())

    def test_csrf_is_required_for_writes(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            "/api/login",
            data={"email": self.patient.email, "password": "Patient123!"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_patient_cannot_read_another_patients_data(self):
        other_appointment = Appointment.objects.create(
            id="apt_other",
            patient=self.other_profile,
            doctor=self.doctor,
            created_by=self.other_patient,
            patient_name=self.other_profile.name,
            patient_email=self.other_profile.email,
            doctor_name=self.doctor.name,
            service_name=self.service.name,
            appointment_date=self.visit_date,
            appointment_time=dt.time(9, 0),
            status="pending",
        )
        TreatmentRecord.objects.create(
            id="rec_other",
            appointment=other_appointment,
            patient=self.other_profile,
            doctor=self.doctor,
            patient_name=self.other_profile.name,
            doctor_name=self.doctor.name,
            treatment_date=dt.date.today(),
            procedure=self.service.name,
            diagnosis="Routine visit",
        )
        client = Client()
        client.force_login(self.patient)
        appointments = client.get("/api/appointments").json()["appointments"]
        records = client.get("/api/records").json()["records"]
        self.assertEqual(appointments, [])
        self.assertEqual(records, [])

    def test_guest_cannot_list_private_appointments(self):
        response = Client().get("/api/appointments")
        self.assertEqual(response.status_code, 401)

    def test_patient_books_available_slot_and_token_is_idempotent(self):
        client, token = self.csrf_client()
        client.force_login(self.patient)
        payload = {
            "doctor": self.doctor.name,
            "service": self.service.name,
            "date": self.visit_date.isoformat(),
            "time": "09:00",
            "notes": "Sensitive tooth",
            "booking_token": "booking_test_token",
        }
        response = self.post_json(client, token, "/api/appointments", payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["appointment"]["status"], "pending")
        replay = self.post_json(client, token, "/api/appointments", payload)
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.json()["replayed"])
        self.assertEqual(Appointment.objects.filter(booking_token="booking_test_token").count(), 1)

    def test_booking_revalidates_service_and_availability(self):
        client, token = self.csrf_client()
        client.force_login(self.patient)
        invalid_service = self.post_json(
            client,
            token,
            "/api/appointments",
            {
                "doctor": self.doctor.name,
                "service": "Not a clinic service",
                "date": self.visit_date.isoformat(),
                "time": "09:00",
            },
        )
        self.assertEqual(invalid_service.status_code, 400)
        unavailable = self.post_json(
            client,
            token,
            "/api/appointments",
            {
                "doctor": self.doctor.name,
                "service": self.service.name,
                "date": self.visit_date.isoformat(),
                "time": "10:00",
            },
        )
        self.assertEqual(unavailable.status_code, 409)

    def test_doctor_accepting_slot_cancels_competing_pending_request(self):
        first = Appointment.objects.create(
            id="apt_first",
            patient=self.profile,
            doctor=self.doctor,
            created_by=self.patient,
            patient_name=self.profile.name,
            patient_email=self.profile.email,
            doctor_name=self.doctor.name,
            service_name=self.service.name,
            appointment_date=self.visit_date,
            appointment_time=dt.time(9, 0),
            status="pending",
        )
        second = Appointment.objects.create(
            id="apt_second",
            patient=self.other_profile,
            doctor=self.doctor,
            created_by=self.other_patient,
            patient_name=self.other_profile.name,
            patient_email=self.other_profile.email,
            doctor_name=self.doctor.name,
            service_name=self.service.name,
            appointment_date=self.visit_date,
            appointment_time=dt.time(9, 0),
            status="pending",
        )
        client, token = self.csrf_client()
        client.force_login(self.doctor)
        response = self.patch_json(client, token, "/api/appointments", {"id": first.id, "status": "approved"})
        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, "approved")
        self.assertEqual(second.status, "cancelled")

    def test_completed_status_requires_treatment_record(self):
        item = Appointment.objects.create(
            id="apt_needs_record",
            patient=self.profile,
            doctor=self.doctor,
            created_by=self.patient,
            patient_name=self.profile.name,
            patient_email=self.profile.email,
            doctor_name=self.doctor.name,
            service_name=self.service.name,
            appointment_date=dt.date.today(),
            appointment_time=dt.time(8, 0),
            status="approved",
        )
        client, token = self.csrf_client()
        client.force_login(self.doctor)
        response = self.patch_json(client, token, "/api/appointments", {"id": item.id, "status": "completed"})
        self.assertEqual(response.status_code, 409)

    def test_treatment_record_completes_appointment_and_calculates_balance(self):
        item = Appointment.objects.create(
            id="apt_treatment",
            patient=self.profile,
            doctor=self.doctor,
            created_by=self.patient,
            patient_name=self.profile.name,
            patient_email=self.profile.email,
            doctor_name=self.doctor.name,
            service_name=self.service.name,
            appointment_date=dt.date.today(),
            appointment_time=dt.time(8, 0),
            status="approved",
        )
        client, token = self.csrf_client()
        client.force_login(self.doctor)
        response = self.post_json(
            client,
            token,
            "/api/records",
            {
                "appointment_id": item.id,
                "patient_id": self.profile.id,
                "treatment_date": dt.date.today().isoformat(),
                "procedure": self.service.name,
                "diagnosis": "Plaque accumulation",
                "amount_charged": "1500",
                "amount_paid": "1000",
                "next_visit": self.visit_date.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["record"]["balance"], 500.0)
        item.refresh_from_db()
        self.assertEqual(item.status, "completed")
        self.assertTrue(Notification.objects.filter(recipient=self.patient, notification_type="treatment_created").exists())

    def test_doctor_service_crud_and_reports(self):
        client, token = self.csrf_client()
        client.force_login(self.doctor)
        create = self.post_json(
            client,
            token,
            "/api/services",
            {"name": "Dental X-ray", "description": "Diagnostic imaging for dental assessment."},
        )
        self.assertEqual(create.status_code, 201)
        service_id = create.json()["service"]["id"]
        self.assertTrue(Service.objects.filter(id=service_id).exists())
        report = client.get("/api/reports")
        self.assertEqual(report.status_code, 200)
        self.assertIn("appointments", report.json())

    def test_notifications_can_be_marked_read(self):
        notification = Notification.objects.create(
            id="ntf_test",
            recipient=self.patient,
            notification_type="appointment_status",
            title="Appointment accepted",
            message="Your appointment was accepted.",
        )
        client, token = self.csrf_client()
        client.force_login(self.patient)
        response = self.patch_json(client, token, "/api/notifications", {"id": notification.id})
        self.assertEqual(response.status_code, 200)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_message_requires_opposite_roles(self):
        client, token = self.csrf_client()
        client.force_login(self.patient)
        response = self.post_json(
            client,
            token,
            "/api/messages",
            {"recipient_id": self.doctor.id, "body": "I have a question about my visit."},
        )
        self.assertEqual(response.status_code, 201)
        invalid = self.post_json(
            client,
            token,
            "/api/messages",
            {"recipient_id": self.other_patient.id, "body": "This should not be allowed."},
        )
        self.assertEqual(invalid.status_code, 403)

    def test_two_clients_keep_separate_sessions(self):
        first_client = Client()
        second_client = Client()
        first_client.force_login(self.patient)
        second_client.force_login(self.other_patient)
        self.assertEqual(first_client.get("/api/session").json()["user"]["id"], self.patient.id)
        self.assertEqual(second_client.get("/api/session").json()["user"]["id"], self.other_patient.id)

    def test_public_feedback_and_availability_remain_accessible(self):
        client, token = self.csrf_client()
        feedback = self.post_json(
            client,
            token,
            "/api/feedback",
            {"name": "Clinic Visitor", "rating": 5, "message": "The clinic staff were very helpful."},
        )
        self.assertEqual(feedback.status_code, 201)
        availability = client.get("/api/availability")
        self.assertEqual(availability.status_code, 200)
        self.assertEqual(len(availability.json()["availability"]), 1)
