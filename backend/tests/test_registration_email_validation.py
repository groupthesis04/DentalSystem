"""The Abstract email gate cannot be bypassed during patient registration."""

import datetime as dt
import io
import json
import os
import re
from unittest import mock

from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from accounts.models import PatientAccountVerification, PatientProfile, User
from accounts.email_validation import validate_email_address
from scheduling.models import Appointment


VALID_RESULT = {
    "valid": True,
    "status": "valid",
    "message": "Email address is valid.",
}


@override_settings(
    SMS_ENABLED=True,
    SEMAPHORE_API_KEY="fake-key",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class RegistrationEmailValidationTests(TestCase):
    def setUp(self):
        cache.clear()
        validator = mock.patch("accounts.views.validate_email_address", return_value=VALID_RESULT)
        self.validate_email = validator.start()
        self.addCleanup(validator.stop)
        sender = mock.patch("accounts.views.sms_provider.send", return_value=("123", "submitted"))
        self.sms_send = sender.start()
        self.addCleanup(sender.stop)

    def payload(self, **overrides):
        values = {
            "first_name": "Juan",
            "middle_name": "Dela",
            "last_name": "Cruz",
            "email": "juan@example.com",
            "phone": "+639123456789",
            "birthdate": "2000-01-01",
            "password": "NewPatient123!",
            "role": "patient",
        }
        values.update(overrides)
        return values

    def register(self, **overrides):
        return self.client.post(
            "/api/register", data=self.payload(**overrides), content_type="application/json",
        )

    def check_email(self, email, *, client=None):
        return (client or self.client).post(
            "/api/email-validation", data={"email": email}, content_type="application/json",
        )

    def assert_no_registration_side_effects(self):
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(PatientProfile.objects.count(), 0)
        self.assertEqual(PatientAccountVerification.objects.count(), 0)
        self.sms_send.assert_not_called()

    def reputation_response(self, **deliverability_changes):
        deliverability = {
            "status": "deliverable",
            "is_format_valid": True,
            "is_mx_valid": True,
            "is_smtp_valid": True,
        }
        deliverability.update(deliverability_changes)
        return json.dumps({
            "email_address": "juan@example.com",
            "email_deliverability": deliverability,
            "email_quality": {"is_disposable": False, "is_catchall": False},
        }).encode("utf-8")

    def test_email_endpoint_normalizes_email_and_returns_only_public_fields(self):
        response = self.check_email("  JUAN@EXAMPLE.COM  ")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), VALID_RESULT)
        self.validate_email.assert_called_once_with("juan@example.com")
        self.assert_no_registration_side_effects()

    def test_invalid_syntax_stops_before_the_provider(self):
        self.validate_email.side_effect = validate_email_address
        with mock.patch.dict(os.environ, {"ABSTRACT_EMAIL_REPUTATION_API_KEY": "fake-key"}):
            with mock.patch("accounts.email_validation.urlopen") as transport:
                checked = self.check_email("invalid-address")
                registered = self.register(email="invalid-address", email_valid=True)

        self.assertEqual(checked.status_code, 200)
        self.assertFalse(checked.json()["valid"])
        self.assertGreaterEqual(registered.status_code, 400)
        transport.assert_not_called()
        self.assert_no_registration_side_effects()

    def test_registered_email_skips_the_provider_for_check_and_registration(self):
        User.objects.create_user(
            email="juan@example.com", password="Existing123!", name="Juan Dela Cruz",
            role="patient",
        )

        checked = self.check_email("JUAN@EXAMPLE.COM")
        registered = self.register(email="JUAN@EXAMPLE.COM")

        self.assertEqual(checked.status_code, 200)
        self.assertEqual(checked.json()["status"], "already_registered")
        self.assertEqual(registered.status_code, 409)
        self.assertIn("already uses this email", str(checked.json()).lower())
        self.assertIn("already uses this email", str(registered.json()).lower())
        self.validate_email.assert_not_called()
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(PatientProfile.objects.count(), 0)
        self.assertEqual(PatientAccountVerification.objects.count(), 0)
        self.sms_send.assert_not_called()

    def test_direct_registration_rejects_invalid_disposable_and_uncertain_email_without_sms(self):
        cases = (
            ("invalid", "This email address could not be verified. Please check the address and try again."),
            ("disposable", "Temporary or disposable email addresses are not allowed."),
            ("unknown", "This email address could not be fully verified. Please check the address or try another email."),
            ("service_unavailable", "Email validation is temporarily unavailable. Please try again."),
        )
        for status, message in cases:
            with self.subTest(status=status):
                cache.clear()
                self.validate_email.return_value = {
                    "valid": False, "status": status, "message": message,
                }

                response = self.register(email_valid=True)

                self.assertGreaterEqual(response.status_code, 400)
                self.assertIn(message, str(response.json()))
                self.assert_no_registration_side_effects()

    def test_invalid_email_never_starts_existing_patient_sms_challenge(self):
        profile = PatientProfile.objects.create(
            id="pat_invalid_email_gate",
            first_name="Juan", middle_name="Dela", last_name="Cruz",
            email="juan@example.com", birthdate=dt.date(2000, 1, 1),
            mobile_number="09123456789",
        )
        self.validate_email.return_value = {
            "valid": False,
            "status": "invalid",
            "message": "This email address could not be verified. Please check the address and try again.",
        }

        response = self.register(email_valid=True)

        self.assertGreaterEqual(response.status_code, 400)
        profile.refresh_from_db()
        self.assertIsNone(profile.user_id)
        self.assertEqual(PatientProfile.objects.count(), 1)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(PatientAccountVerification.objects.count(), 0)
        self.sms_send.assert_not_called()

    def test_reputation_invalid_email_never_starts_existing_patient_sms_challenge(self):
        profile = PatientProfile.objects.create(
            id="pat_invalid_reputation_gate",
            first_name="Juan", middle_name="Dela", last_name="Cruz",
            email="juan@example.com", birthdate=dt.date(2000, 1, 1),
            mobile_number="09123456789",
        )
        self.validate_email.side_effect = validate_email_address
        body = self.reputation_response(status="undeliverable", is_smtp_valid=False)
        with mock.patch.dict(os.environ, {"ABSTRACT_EMAIL_REPUTATION_API_KEY": "fake-key"}):
            with mock.patch("accounts.email_validation.urlopen", return_value=io.BytesIO(body)) as transport:
                response = self.register(email_valid=True)

        self.assertEqual(response.status_code, 400)
        self.assertIn("could not be verified", response.json()["error"])
        self.assertEqual(transport.call_count, 1)
        profile.refresh_from_db()
        self.assertIsNone(profile.user_id)
        self.assertEqual(PatientProfile.objects.count(), 1)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(PatientAccountVerification.objects.count(), 0)
        self.sms_send.assert_not_called()

    def test_suggestion_is_shown_without_rewriting_submitted_email(self):
        self.validate_email.side_effect = validate_email_address
        body = json.dumps({
            "email_address": "juan@gmial.com",
            "suggested_correction": "juan@gmail.com",
            "email_deliverability": {
                "status": "undeliverable",
                "is_format_valid": True,
                "is_mx_valid": False,
                "is_smtp_valid": False,
            },
            "email_quality": {"is_disposable": False, "is_catchall": False},
        }).encode("utf-8")
        with mock.patch.dict(os.environ, {"ABSTRACT_EMAIL_REPUTATION_API_KEY": "fake-key"}):
            with mock.patch("accounts.email_validation.urlopen", return_value=io.BytesIO(body)) as transport:
                checked = self.check_email("juan@gmial.com")
                registered = self.register(email="juan@gmial.com", email_valid=True)

        self.assertEqual(checked.status_code, 200)
        self.assertFalse(checked.json()["valid"])
        self.assertEqual(checked.json()["status"], "invalid")
        self.assertEqual(checked.json()["suggested_email"], "juan@gmail.com")
        self.assertGreaterEqual(registered.status_code, 400)
        self.assertEqual(transport.call_count, 1)
        self.assert_no_registration_side_effects()

    def test_provider_details_never_appear_in_endpoint_or_registration_errors(self):
        secret = "test-private-abstract-key"
        self.validate_email.return_value = {
            "valid": False,
            "status": "service_unavailable",
            "message": "Email validation is temporarily unavailable. Please try again.",
            "raw_provider": {"api_key": secret, "url": f"https://example.test/?api_key={secret}"},
        }

        checked = self.check_email("juan@example.com")
        registered = self.register()

        self.assertEqual(checked.status_code, 200)
        self.assertFalse(checked.json()["valid"])
        self.assertGreaterEqual(registered.status_code, 400)
        self.assertNotIn(secret, checked.content.decode())
        self.assertNotIn(secret, registered.content.decode())
        self.assertNotIn("raw_provider", checked.json())
        self.assert_no_registration_side_effects()

    def test_valid_email_creates_new_patient_normally(self):
        self.validate_email.side_effect = validate_email_address
        body = self.reputation_response()
        with mock.patch.dict(os.environ, {"ABSTRACT_EMAIL_REPUTATION_API_KEY": "fake-key"}):
            with mock.patch("accounts.email_validation.urlopen", return_value=io.BytesIO(body)) as transport:
                checked = self.check_email("  JUAN@EXAMPLE.COM  ")
                response = self.register(email="  JUAN@EXAMPLE.COM  ")

        self.assertEqual(checked.status_code, 200)
        self.assertEqual(checked.json(), VALID_RESULT)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(self.validate_email.call_count, 2)
        self.assertEqual(transport.call_count, 1, "Registration should reuse the recent normalized-email cache")
        user = User.objects.get(email="juan@example.com")
        profile = PatientProfile.objects.get(user=user)
        self.assertEqual(profile.email, user.email)
        self.assertEqual(profile.birthdate, dt.date(2000, 1, 1))
        self.assertEqual(PatientAccountVerification.objects.count(), 0)
        self.sms_send.assert_not_called()

    def test_valid_email_keeps_existing_patient_sms_verification_and_history(self):
        profile = PatientProfile.objects.create(
            id="pat_existing_email_validation",
            first_name="Juan", middle_name="Dela", last_name="Cruz",
            email="juan@example.com", birthdate=dt.date(2000, 1, 1),
            mobile_number="09123456789", notes="Existing clinic notes",
        )
        appointment = Appointment.objects.create(
            id="apt_existing_email_validation",
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

        self.validate_email.side_effect = validate_email_address
        body = self.reputation_response()
        with mock.patch.dict(os.environ, {"ABSTRACT_EMAIL_REPUTATION_API_KEY": "fake-key"}):
            with mock.patch("accounts.email_validation.urlopen", return_value=io.BytesIO(body)) as transport:
                response = self.register()

        self.assertEqual(response.status_code, 202, response.content)
        self.validate_email.assert_called_once_with("juan@example.com")
        self.assertEqual(transport.call_count, 1)
        self.assertTrue(response.json()["verification_required"])
        self.assertEqual(PatientAccountVerification.objects.count(), 1)
        self.assertFalse(User.objects.filter(email="juan@example.com").exists())
        self.sms_send.assert_called_once()
        self.assertEqual(self.sms_send.call_args.args[0], "639123456789")
        code = re.search(r"code is ([0-9]{6})", self.sms_send.call_args.args[1]).group(1)

        verified = self.client.post(
            "/api/account-verification/verify",
            data={"verification_token": response.json()["verification_token"], "code": code},
            content_type="application/json",
        )
        self.assertEqual(verified.status_code, 201, verified.content)
        profile.refresh_from_db()
        appointment.refresh_from_db()
        self.assertIsNotNone(profile.user_id)
        self.assertEqual(profile.id, "pat_existing_email_validation")
        self.assertEqual(profile.mobile_number, "09123456789")
        self.assertEqual(profile.notes, "Existing clinic notes")
        self.assertEqual(appointment.patient_id, profile.id)
        self.assertEqual(PatientProfile.objects.count(), 1)

    def test_email_endpoint_has_independent_rate_limit(self):
        limited = None
        for index in range(100):
            response = self.check_email(f"juan{index}@example.com")
            if response.status_code == 429:
                limited = response
                break

        self.assertIsNotNone(limited, "Email-check endpoint must limit repeated requests")
        provider_calls = self.validate_email.call_count
        again = self.check_email("one-more@example.com")
        self.assertEqual(again.status_code, 429)
        self.assertEqual(self.validate_email.call_count, provider_calls)

    def test_email_endpoint_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        rejected = self.check_email("juan@example.com", client=client)
        self.assertEqual(rejected.status_code, 403)
        self.validate_email.assert_not_called()

        token = client.get("/api/session").json()["csrf_token"]
        accepted = client.post(
            "/api/email-validation", data={"email": "juan@example.com"},
            content_type="application/json", HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(accepted.status_code, 200)
        self.validate_email.assert_called_once_with("juan@example.com")
