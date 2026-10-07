import datetime as dt
import json

from django.test import Client, TestCase

from accounts.models import PatientProfile, User
from scheduling.models import Appointment


class PatientAppointmentContactTests(TestCase):
    def test_clinic_patient_edit_refreshes_appointment_contact_details(self):
        doctor = User.objects.create_user(
            email="contact-doctor@example.com",
            password="TestDoctor123!",
            name="Dr. Contact",
            role="doctor",
        )
        patient = PatientProfile.objects.create(
            id="pat_manual_contact",
            first_name="Old",
            last_name="Name",
            email="old-contact@example.com",
            mobile_number="09123456700",
        )
        appointment = Appointment.objects.create(
            id="apt_manual_contact",
            patient=patient,
            doctor=doctor,
            doctor_name=doctor.name,
            patient_name=patient.name,
            patient_email=patient.email,
            patient_phone=patient.phone,
            service_name="Dental Cleaning",
            appointment_date=dt.date.today() + dt.timedelta(days=7),
            appointment_time=dt.time(10, 0),
            status="approved",
            source="manual",
        )
        client = Client()
        client.force_login(doctor)

        updated = client.patch(
            "/api/patients",
            data=json.dumps({
                "id": patient.id,
                "first_name": "New",
                "last_name": "Name",
                "email": "new-contact@example.com",
                "phone_number": "09123456701",
                "mobile_number": "09123456701",
                "birthdate": "1990-01-01",
                "sex": "female",
                "address": "123 Main Street",
                "nationality": "Filipino",
                "occupation": "Teacher",
            }),
            content_type="application/json",
        )

        self.assertEqual(updated.status_code, 200)
        listed = client.get("/api/appointments")
        self.assertEqual(listed.status_code, 200)
        item = next(
            item for item in listed.json()["appointments"]
            if item["id"] == appointment.id
        )
        self.assertEqual(item["patient_name"], "New Name")
        self.assertEqual(item["patient_email"], "new-contact@example.com")
        self.assertEqual(item["patient_phone"], "09123456701")
