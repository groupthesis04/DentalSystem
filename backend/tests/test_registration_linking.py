"""Registration regression tests for clinic-created patient records."""

import datetime as dt
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from accounts.models import PatientProfile, User
from accounts.management.commands.import_legacy_data import Command as LegacyImportCommand
from clinic.models import Service
from communications.models import SmsMessage, SmsRule
from records.models import TreatmentRecord
from scheduling.models import Appointment, AvailabilitySlot


class RegistrationLinkingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.birthdate = dt.date(2000, 1, 1)

    def registration_payload(self, **overrides):
        payload = {
            "first_name": "Juan",
            "middle_name": "Dela",
            "last_name": "Cruz",
            "email": "juan@example.com",
            "phone": "+639123456789",
            "birthdate": self.birthdate.isoformat(),
            "password": "NewPatient123!",
            "role": "patient",
        }
        payload.update(overrides)
        return payload

    def register(self, **overrides):
        return self.client.post(
            "/api/register",
            data=self.registration_payload(**overrides),
            content_type="application/json",
        )

    def clinic_profile(self, **overrides):
        values = {
            "id": "pat_juan_existing",
            "first_name": "Juan",
            "middle_name": "Dela",
            "last_name": "Cruz",
            "email": "juan@example.com",
            "birthdate": self.birthdate,
            "mobile_number": "09123456789",
            "notes": "Existing clinic notes",
        }
        values.update(overrides)
        return PatientProfile.objects.create(**values)

    def doctor(self):
        return User.objects.create_user(
            id="usr_registration_doctor",
            email="doctor@example.com",
            password="Doctor123!",
            name="Dr. Maria Santos",
            role="doctor",
            is_staff=True,
        )

    def assert_registration_refused_without_changes(self, response, profile_count=1):
        self.assertGreaterEqual(response.status_code, 400)
        self.assertIn("error", response.json())
        self.assertFalse(User.objects.filter(email="juan@example.com").exists())
        self.assertEqual(PatientProfile.objects.count(), profile_count)

    def test_matching_clinic_record_links_account_without_changing_history(self):
        profile = self.clinic_profile()
        appointment = Appointment.objects.create(
            id="apt_juan_existing",
            patient=profile,
            patient_name=profile.name,
            patient_email=profile.email,
            patient_phone=profile.phone,
            doctor_name="Dr. Maria Santos",
            service_name="Tooth Extraction",
            appointment_date=dt.date.today() + dt.timedelta(days=7),
            appointment_time=dt.time(8),
            status="pending",
            source="manual",
        )
        record = TreatmentRecord.objects.create(
            id="rec_juan_existing",
            patient=profile,
            appointment=appointment,
            patient_name=profile.name,
            doctor_name="Dr. Maria Santos",
            treatment_date=dt.date.today(),
            procedure="Tooth Extraction",
            amount_charged=Decimal("1200.00"),
            amount_paid=Decimal("300.00"),
            balance=Decimal("900.00"),
            next_visit=dt.date.today() + dt.timedelta(days=30),
        )
        rule = SmsRule.objects.create(key="registration_test", template="Reminder")
        sms = SmsMessage.objects.create(
            id="sms_juan_existing",
            event_key="registration-existing-history",
            rule=rule,
            patient=profile,
            appointment=appointment,
            record=record,
            patient_name=profile.name,
            phone=profile.phone,
            body="Reminder",
            scheduled_for=timezone.now(),
            expires_at=timezone.now() + dt.timedelta(days=1),
        )

        response = self.register(email="  JUAN@example.com  ")

        self.assertEqual(response.status_code, 201)
        profile.refresh_from_db()
        self.assertIsNotNone(profile.user_id)
        self.assertEqual(profile.user.email, "juan@example.com")
        self.assertEqual(profile.id, "pat_juan_existing")
        self.assertEqual(PatientProfile.objects.count(), 1)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(self.client.get("/api/session").json()["user"]["id"], profile.user_id)
        appointment.refresh_from_db()
        record.refresh_from_db()
        sms.refresh_from_db()
        self.assertEqual(appointment.patient_id, profile.id)
        self.assertEqual(record.patient_id, profile.id)
        self.assertEqual(sms.patient_id, profile.id)
        self.assertEqual(record.balance, Decimal("900.00"))
        self.assertEqual(record.next_visit, dt.date.today() + dt.timedelta(days=30))

    def test_blank_email_walk_in_links_by_normalized_name_phone_and_birthdate(self):
        profile = self.clinic_profile(id="pat_walk_in", email="", mobile_number="639123456789")

        response = self.register(
            first_name="  JUAN  ",
            middle_name=" dela ",
            last_name=" CRUZ ",
            phone="09123456789",
        )

        self.assertEqual(response.status_code, 201)
        profile.refresh_from_db()
        self.assertIsNotNone(profile.user_id)
        self.assertEqual(profile.email, "juan@example.com")
        self.assertEqual(profile.id, "pat_walk_in")
        self.assertEqual(PatientProfile.objects.count(), 1)

    def test_new_patient_creates_one_linked_profile(self):
        response = self.register()

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="juan@example.com")
        profile = PatientProfile.objects.get(user=user)
        self.assertEqual(PatientProfile.objects.count(), 1)
        self.assertEqual(profile.birthdate, self.birthdate)
        self.assertEqual(profile.name, "Juan Dela Cruz")

    def test_existing_account_email_is_rejected_without_creating_another_profile(self):
        user = User.objects.create_user(
            id="usr_juan_existing",
            email="juan@example.com",
            password="Existing123!",
            name="Juan Dela Cruz",
            phone="09123456789",
            role="patient",
        )
        profile = self.clinic_profile(user=user)

        response = self.register(email="JUAN@EXAMPLE.COM")

        self.assertEqual(response.status_code, 409)
        self.assertIn("log in", response.json()["error"].lower())
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(PatientProfile.objects.count(), 1)
        profile.refresh_from_db()
        self.assertEqual(profile.user_id, user.id)

    def test_matching_email_with_wrong_phone_or_birthdate_does_not_claim_record(self):
        profile = self.clinic_profile()
        for changes in (
            {"phone": "09998887777"},
            {"birthdate": "2001-01-01"},
        ):
            with self.subTest(changes=changes):
                response = self.register(**changes)
                self.assert_registration_refused_without_changes(response)
                profile.refresh_from_db()
                self.assertIsNone(profile.user_id)

    def test_same_name_alone_cannot_claim_a_walk_in_record(self):
        profile = self.clinic_profile(email="")

        response = self.register(phone="09998887777")

        self.assert_registration_refused_without_changes(response)
        profile.refresh_from_db()
        self.assertIsNone(profile.user_id)

    def test_existing_record_with_different_email_is_not_duplicated_or_claimed(self):
        profile = self.clinic_profile(email="old.juan@example.com")

        response = self.register()

        self.assert_registration_refused_without_changes(response)
        profile.refresh_from_db()
        self.assertIsNone(profile.user_id)
        self.assertEqual(profile.email, "old.juan@example.com")

    def test_existing_record_without_birthdate_requires_verification(self):
        profile = self.clinic_profile(birthdate=None)

        response = self.register()

        self.assert_registration_refused_without_changes(response)
        profile.refresh_from_db()
        self.assertIsNone(profile.user_id)

    def test_phone_match_to_dob_missing_record_requires_clinic_verification(self):
        profile = self.clinic_profile(
            first_name="Maria", middle_name="", last_name="Santos", email="", birthdate=None
        )

        response = self.register()

        self.assert_registration_refused_without_changes(response)
        profile.refresh_from_db()
        self.assertIsNone(profile.user_id)

    def test_ambiguous_matching_records_are_not_linked(self):
        first = self.clinic_profile()
        second = self.clinic_profile(
            id="pat_juan_duplicate",
            first_name="Other",
            middle_name="",
            last_name="Person",
        )

        response = self.register()

        self.assert_registration_refused_without_changes(response, profile_count=2)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertIsNone(first.user_id)
        self.assertIsNone(second.user_id)

    def test_failed_account_creation_rolls_back_insert(self):
        profile = self.clinic_profile()
        create_user = User.objects.create_user

        def create_then_fail(**kwargs):
            create_user(**kwargs)
            raise IntegrityError("Simulated failure after user insert")

        with mock.patch.object(User.objects, "create_user", side_effect=create_then_fail) as create_mock:
            response = self.register()

        create_mock.assert_called_once()
        self.assert_registration_refused_without_changes(response)
        profile.refresh_from_db()
        self.assertIsNone(profile.user_id)

    def test_registration_requires_birthdate_for_safe_linking(self):
        response = self.register(birthdate="")

        self.assertGreaterEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email="juan@example.com").exists())
        self.assertEqual(PatientProfile.objects.count(), 0)

    def test_admin_cannot_add_duplicate_with_changed_name_and_email(self):
        existing = self.clinic_profile()
        doctor = self.doctor()
        self.client.force_login(doctor)

        response = self.client.post(
            "/api/patients",
            data={
                "first_name": "Carlos",
                "last_name": "Ramos",
                "email": "carlos@example.com",
                "phone_number": "",
                "mobile_number": "+639123456789",
                "birthdate": self.birthdate.isoformat(),
                "sex": "male",
                "address": "123 Main Street",
                "nationality": "Filipino",
                "occupation": "Teacher",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("error", response.json())
        self.assertEqual(PatientProfile.objects.count(), 1)
        existing.refresh_from_db()
        self.assertEqual(existing.name, "Juan Dela Cruz")
        self.assertEqual(existing.email, "juan@example.com")

    def test_repeated_manual_walk_in_without_email_or_birthdate_is_rejected(self):
        doctor = self.doctor()
        self.client.force_login(doctor)
        Service.objects.create(id="svc_walk_in", name="Cleaning", description="Routine cleaning")
        first_date = dt.date.today() + dt.timedelta(days=7)
        second_date = first_date + dt.timedelta(days=1)
        for index, visit_date in enumerate((first_date, second_date), start=1):
            AvailabilitySlot.objects.create(
                id=f"slot_walk_in_{index}",
                doctor=doctor,
                doctor_name=doctor.name,
                date=visit_date,
                time=dt.time(9),
            )

        def book_walk_in(visit_date, phone):
            return self.client.post(
                "/api/appointments",
                data={
                    "doctor": doctor.name,
                    "service": "Cleaning",
                    "date": visit_date.isoformat(),
                    "time": "09:00",
                    "name": "Maria Santos",
                    "phone": phone,
                    "email": "",
                    "birthdate": "",
                },
                content_type="application/json",
            )

        first = book_walk_in(first_date, "09123456780")
        self.assertEqual(first.status_code, 201)
        patient_id = first.json()["patient"]["id"]
        second = book_walk_in(second_date, "+639123456780")

        self.assertEqual(second.status_code, 409)
        self.assertIn("error", second.json())
        self.assertEqual(PatientProfile.objects.count(), 1)
        self.assertEqual(Appointment.objects.count(), 1)
        self.assertEqual(Appointment.objects.get().patient_id, patient_id)

    def test_legacy_login_and_session_do_not_claim_plausible_unlinked_profile(self):
        profile = self.clinic_profile()
        user = User.objects.create_user(
            id="usr_legacy_no_profile",
            email="juan@example.com",
            password="LegacyPatient123!",
            name="Juan Dela Cruz",
            phone="+639123456789",
            role="patient",
        )

        login_response = self.client.post(
            "/api/login",
            data={"email": user.email, "password": "LegacyPatient123!"},
            content_type="application/json",
        )
        session_response = self.client.get("/api/session")

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(session_response.status_code, 200)
        self.assertTrue(login_response.json()["user"]["profile_verification_required"])
        self.assertTrue(session_response.json()["user"]["profile_verification_required"])
        self.assertEqual(PatientProfile.objects.count(), 1)
        self.assertFalse(PatientProfile.objects.filter(user=user).exists())
        profile.refresh_from_db()
        self.assertIsNone(profile.user_id)


class LegacyImportLinkingTests(TestCase):
    def run_import(self, rows):
        output = StringIO()
        warnings = StringIO()

        def table_rows(_command, table_name):
            return rows.get(table_name, [])

        with mock.patch.object(LegacyImportCommand, "table_rows", autospec=True, side_effect=table_rows):
            call_command("import_legacy_data", stdout=output, stderr=warnings)
        return output.getvalue(), warnings.getvalue()

    def test_different_user_and_clinic_profile_ids_remain_unlinked_and_keep_history(self):
        next_visit = dt.date.today() + dt.timedelta(days=30)
        rows = {
            "users": [
                {
                    "id": "usr_legacy_juan",
                    "name": "Juan Dela Cruz",
                    "email": "juan@example.com",
                    "phone": "+639123456789",
                    "role": "patient",
                    "password_hash": "legacy-password-hash",
                }
            ],
            "patient_profiles": [
                {
                    "id": "pat_legacy_juan",
                    "name": "Juan Dela Cruz",
                    "email": "juan@example.com",
                    "phone": "09123456789",
                    "birthdate": "2000-01-01",
                    "notes": "Clinic history",
                }
            ],
            "appointments": [
                {
                    "id": "apt_legacy_juan",
                    "patient_id": "pat_legacy_juan",
                    "doctor_name": "Dr. Maria Santos",
                    "service": "Cleaning",
                    "date": (dt.date.today() + dt.timedelta(days=7)).isoformat(),
                    "time": "09:00",
                    "status": "pending",
                }
            ],
            "treatments": [
                {
                    "id": "rec_legacy_juan",
                    "patient_id": "pat_legacy_juan",
                    "appointment_id": "apt_legacy_juan",
                    "doctor_name": "Dr. Maria Santos",
                    "procedure": "Cleaning",
                    "treatment_date": dt.date.today().isoformat(),
                    "amount_charged": "1000.00",
                    "amount_paid": "300.00",
                    "balance": "700.00",
                    "next_visit": next_visit.isoformat(),
                }
            ],
        }

        _, warnings = self.run_import(rows)
        self.run_import(rows)

        profile = PatientProfile.objects.get(id="pat_legacy_juan")
        appointment = Appointment.objects.get(id="apt_legacy_juan")
        record = TreatmentRecord.objects.get(id="rec_legacy_juan")
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(PatientProfile.objects.count(), 1)
        self.assertIsNone(profile.user_id)
        self.assertEqual(appointment.patient_id, profile.id)
        self.assertEqual(record.patient_id, profile.id)
        self.assertEqual(record.appointment_id, appointment.id)
        self.assertEqual(record.balance, Decimal("700.00"))
        self.assertEqual(record.next_visit, next_visit)
        self.assertIn("Review legacy patient link", warnings)

    def test_matching_legacy_user_and_profile_ids_link_explicitly(self):
        rows = {
            "users": [
                {
                    "id": "pat_legacy_same_id",
                    "name": "Maria Santos",
                    "email": "maria@example.com",
                    "phone": "09123456780",
                    "role": "patient",
                    "password_hash": "legacy-password-hash",
                }
            ],
            "patient_profiles": [
                {
                    "id": "pat_legacy_same_id",
                    "name": "Maria Santos",
                    "email": "maria@example.com",
                    "phone": "09123456780",
                    "birthdate": "1998-05-10",
                }
            ],
        }

        self.run_import(rows)

        profile = PatientProfile.objects.get(id="pat_legacy_same_id")
        self.assertEqual(profile.user_id, "pat_legacy_same_id")
        self.assertEqual(PatientProfile.objects.count(), 1)
        self.assertEqual(User.objects.count(), 1)
