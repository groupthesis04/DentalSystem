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
                "first_name": "New",
                "last_name": "Patient",
                "email": "new.patient@example.com",
                "phone": "09112223333",
                "birthdate": "2000-04-12",
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

    def test_patient_booking_saves_multiple_services_in_order(self):
        second_service = Service.objects.create(
            id="svc_booking_fluoride",
            name="Fluoride Treatment",
            description="Protective fluoride application.",
        )
        client, token = self.csrf_client()
        client.force_login(self.patient)
        response = self.post_json(client, token, "/api/appointments", {
            "doctor": self.doctor.name,
            "services": [self.service.name, second_service.name],
            "date": self.visit_date.isoformat(),
            "time": "09:00",
        })
        self.assertEqual(response.status_code, 201)
        appointment = response.json()["appointment"]
        self.assertEqual(appointment["services"], [self.service.name, second_service.name])
        self.assertEqual(appointment["service"], self.service.name)
        saved = Appointment.objects.get(pk=appointment["id"])
        self.assertEqual(saved.services, [self.service.name, second_service.name])
        self.assertEqual(saved.service_name, self.service.name)
        listed = client.get("/api/appointments").json()["appointments"]
        self.assertEqual(listed[0]["services"], [self.service.name, second_service.name])
        self.assertTrue(Notification.objects.filter(
            recipient=self.doctor,
            message__contains=f"{self.service.name}, {second_service.name}",
        ).exists())

    def test_booking_rejects_invalid_or_duplicate_service_selection(self):
        client, token = self.csrf_client()
        client.force_login(self.patient)
        base = {
            "doctor": self.doctor.name,
            "date": self.visit_date.isoformat(),
            "time": "09:00",
        }
        for selection in ([], [self.service.name, self.service.name.lower()], [self.service.name, "Unknown service"], "Oral Prophylaxis"):
            response = self.post_json(client, token, "/api/appointments", {**base, "services": selection})
            self.assertEqual(response.status_code, 400)
        self.assertFalse(Appointment.objects.exists())

    def test_legacy_appointment_returns_single_service_list(self):
        legacy = Appointment.objects.create(
            id="apt_old_single_service",
            patient=self.profile,
            doctor=self.doctor,
            patient_name=self.profile.name,
            doctor_name=self.doctor.name,
            service_name=self.service.name,
            appointment_date=self.visit_date,
            appointment_time=dt.time(9, 0),
        )
        client = Client()
        client.force_login(self.patient)
        appointment = client.get("/api/appointments").json()["appointments"][0]
        self.assertEqual(appointment["id"], legacy.id)
        self.assertEqual(appointment["services"], [self.service.name])
        self.assertEqual(appointment["service"], self.service.name)

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

    def test_treatment_can_use_services_saved_on_appointment_after_catalog_changes(self):
        removed_service = Service.objects.create(
            id="svc_booking_removed",
            name="Ceramic Braces",
            description="A historical booked service.",
        )
        booked_names = [self.service.name, removed_service.name]
        appointment = Appointment.objects.create(
            id="apt_multi_historical",
            patient=self.profile,
            doctor=self.doctor,
            patient_name=self.profile.name,
            doctor_name=self.doctor.name,
            service_name=booked_names[0],
            services=booked_names,
            appointment_date=dt.date.today(),
            appointment_time=dt.time(8, 0),
            status="approved",
        )
        self.service.name = "Renamed Prophylaxis"
        self.service.save(update_fields=["name", "updated_at"])
        removed_service.delete()

        client, token = self.csrf_client()
        client.force_login(self.doctor)
        values = {
            "appointment_id": appointment.id,
            "patient_id": self.profile.id,
            "treatment_date": dt.date.today().isoformat(),
            "diagnosis": "Treatment performed as booked",
        }
        invalid = self.post_json(client, token, "/api/records", {
            **values, "procedures": booked_names + ["Never booked service"],
        })
        self.assertEqual(invalid.status_code, 400)
        saved = self.post_json(client, token, "/api/records", {
            **values, "procedures": booked_names,
        })
        self.assertEqual(saved.status_code, 201)
        self.assertEqual(saved.json()["record"]["procedures"], booked_names)
        edited = self.patch_json(client, token, "/api/records", {
            "id": saved.json()["record"]["id"],
            "patient_id": self.profile.id,
            "treatment_date": dt.date.today().isoformat(),
            "diagnosis": "Updated findings",
            "procedures": booked_names,
        })
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(
            TreatmentRecord.objects.get(id=saved.json()["record"]["id"]).appointment_id,
            appointment.id,
        )
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "completed")

    def test_treatment_record_saves_multiple_services_and_keeps_primary_procedure(self):
        second_service = Service.objects.create(
            id="svc_test_fluoride",
            name="Fluoride Treatment",
            description="Topical fluoride treatment for teeth.",
        )
        client, token = self.csrf_client()
        client.force_login(self.doctor)
        values = {
            "patient_id": self.profile.id,
            "treatment_date": dt.date.today().isoformat(),
            "procedures": [self.service.name, second_service.name],
            "procedure": "Ignored when procedures is provided",
            "diagnosis": "Plaque accumulation",
            "amount_charged": "1500",
            "amount_paid": "1000",
        }
        created = self.post_json(client, token, "/api/records", values)
        self.assertEqual(created.status_code, 201)
        record = created.json()["record"]
        self.assertEqual(record["procedure"], self.service.name)
        self.assertEqual(record["procedures"], [self.service.name, second_service.name])
        self.assertEqual(TreatmentRecord.objects.get(id=record["id"]).procedures, record["procedures"])

        updated = self.patch_json(client, token, "/api/records", {
            **values,
            "id": record["id"],
            "procedures": [second_service.name],
        })
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["record"]["procedure"], second_service.name)
        self.assertEqual(updated.json()["record"]["procedures"], [second_service.name])
        self.assertEqual(TreatmentRecord.objects.filter(id=record["id"]).count(), 1)

        client.force_login(self.patient)
        listed = client.get("/api/records")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["records"][0]["procedures"], [second_service.name])

    def test_treatment_record_validates_each_service_in_multiple_selection(self):
        client, token = self.csrf_client()
        client.force_login(self.doctor)
        values = {
            "patient_id": self.profile.id,
            "treatment_date": dt.date.today().isoformat(),
            "diagnosis": "Routine examination",
        }
        invalid_selections = [
            [],
            "Oral Prophylaxis",
            [self.service.name, "Unknown Service"],
            [self.service.name, " "],
            [self.service.name, self.service.name.lower()],
        ]
        for procedures in invalid_selections:
            with self.subTest(procedures=procedures):
                response = self.post_json(client, token, "/api/records", {
                    **values, "procedures": procedures,
                })
                self.assertEqual(response.status_code, 400)
        self.assertFalse(TreatmentRecord.objects.exists())

    def test_treatment_edit_keeps_historical_services_after_catalog_changes(self):
        deleted_service = Service.objects.create(
            id="svc_test_removed",
            name="Ceramic Braces",
            description="Ceramic orthodontic braces treatment.",
        )
        added_service = Service.objects.create(
            id="svc_test_added",
            name="Fluoride Treatment",
            description="Topical fluoride treatment for teeth.",
        )
        client, token = self.csrf_client()
        client.force_login(self.doctor)
        values = {
            "patient_id": self.profile.id,
            "treatment_date": dt.date.today().isoformat(),
            "procedures": [self.service.name, deleted_service.name],
            "diagnosis": "Orthodontic assessment",
        }
        created = self.post_json(client, token, "/api/records", values)
        self.assertEqual(created.status_code, 201)
        record_id = created.json()["record"]["id"]

        original_name = self.service.name
        removed_name = deleted_service.name
        self.service.name = "Renamed Cleaning Service"
        self.service.save(update_fields=["name", "updated_at"])
        deleted_service.delete()

        edited = self.patch_json(client, token, "/api/records", {
            **values,
            "id": record_id,
            "procedures": [original_name, removed_name, added_service.name],
            "diagnosis": "Updated clinical findings",
        })
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(
            edited.json()["record"]["procedures"],
            [original_name, removed_name, added_service.name],
        )

        for procedures in (
            [original_name, removed_name, "Unknown new service"],
            [original_name, original_name.lower()],
        ):
            with self.subTest(procedures=procedures):
                rejected = self.patch_json(client, token, "/api/records", {
                    **values, "id": record_id, "procedures": procedures,
                })
                self.assertEqual(rejected.status_code, 400)
        stored = TreatmentRecord.objects.get(id=record_id)
        self.assertEqual(stored.procedures, [original_name, removed_name, added_service.name])

    def test_treatment_record_legacy_procedure_serializes_as_one_service(self):
        client, token = self.csrf_client()
        client.force_login(self.doctor)
        response = self.post_json(client, token, "/api/records", {
            "patient_id": self.profile.id,
            "treatment_date": dt.date.today().isoformat(),
            "procedure": self.service.name,
            "diagnosis": "Routine examination",
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["record"]["procedures"], [self.service.name])

        legacy_record = TreatmentRecord.objects.create(
            id="rec_legacy_without_list",
            patient=self.profile,
            patient_name=self.profile.name,
            doctor_name=self.doctor.name,
            treatment_date=dt.date.today(),
            procedure="Historical service name",
        )
        self.assertEqual(legacy_record.procedures, [])
        records = client.get("/api/records").json()["records"]
        historical = next(item for item in records if item["id"] == legacy_record.id)
        self.assertEqual(historical["procedures"], ["Historical service name"])

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
