"""Email OTP password recovery regression tests.

The delivery function is mocked throughout: these tests never send real email.
"""

import datetime as dt
import json
from urllib.error import HTTPError
from unittest.mock import MagicMock, patch

from django.contrib.auth.hashers import check_password
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from accounts.audit_models import AuditEvent
from accounts.models import AccountAuthState, PasswordResetVerification, User
from accounts.password_reset import PasswordResetEmailError, send_password_reset_email


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    RESEND_API_KEY="re_test_password_reset",
    RESEND_FROM_EMAIL="noreply@borjadental.example",
    RESEND_FROM_NAME="BORJA Dental Clinic",
)
class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.patient = User.objects.create_user(
            email="patient@gmail.com",
            password="OldPatient123!",
            name="Patient Example",
            role="patient",
        )
        self.doctor = User.objects.create_user(
            email="doctor@example.com",
            password="OldDoctor123!",
            name="Dr. Example",
            role="doctor",
            is_staff=True,
        )
        sender = patch("accounts.password_reset.send_password_reset_email")
        self.send_email = sender.start()
        self.addCleanup(sender.stop)
        self.client = Client(enforce_csrf_checks=True)
        self.csrf = self.client.get("/api/session").json()["csrf_token"]

    def post(self, endpoint, payload, *, client=None, csrf=None):
        target = client or self.client
        token = csrf if csrf is not None else self.csrf
        return target.post(
            endpoint,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

    def request_reset(self, email=None, **extra):
        return self.post(
            "/api/password-reset/request",
            {"email": self.patient.email if email is None else email, **extra},
        )

    def code_sent(self):
        self.assertTrue(self.send_email.called)
        args, _ = self.send_email.call_args
        self.assertEqual(len(args), 2)
        self.assertRegex(args[1], r"^[0-9]{6}$")
        return args[1]

    def requested_token_and_code(self, email=None):
        response = self.request_reset(email)
        self.assertEqual(response.status_code, 202, response.content)
        return response.json()["reset_token"], self.code_sent()

    def verified_token(self, email=None):
        token, code = self.requested_token_and_code(email)
        response = self.post(
            "/api/password-reset/verify", {"reset_token": token, "code": code}
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["verified"])
        return token

    def confirm(self, token, password="NewPatient456!"):
        return self.post(
            "/api/password-reset/confirm",
            {
                "reset_token": token,
                "new_password": password,
                "confirm_password": password,
            },
        )

    def login_as(self, user, password):
        client = Client(enforce_csrf_checks=True)
        csrf = client.get("/api/session").json()["csrf_token"]
        response = self.post(
            "/api/login",
            {"email": user.email, "password": password},
            client=client,
            csrf=csrf,
        )
        self.assertEqual(response.status_code, 200, response.content)
        return client

    def test_patient_and_doctor_request_code_to_registered_address(self):
        for user in (self.patient, self.doctor):
            with self.subTest(role=user.role):
                self.send_email.reset_mock()
                response = self.request_reset(user.email.upper(), send_otp_to="attacker@example.com")
                self.assertEqual(response.status_code, 202, response.content)
                data = response.json()
                self.assertTrue(data["verification_required"])
                self.assertTrue(data["reset_token"])
                self.assertEqual(data["expires_in"], 300)
                self.assertEqual(data["resend_after"], 60)
                self.assertNotIn(user.email, data["masked_email"])
                code = self.code_sent()
                self.assertEqual(self.send_email.call_args.args[0], user.email)
                self.assertNotIn(code, response.content.decode())
                self.assertNotIn("password", data)
                challenge = PasswordResetVerification.objects.get(user=user)
                self.assertNotEqual(challenge.token_hash, data["reset_token"])
                self.assertNotEqual(challenge.code_hash, code)
                self.assertTrue(check_password(code, challenge.code_hash))
                self.assertEqual(len(challenge.token_hash), 64)
                self.assertGreater(challenge.expires_at, timezone.now())

    def test_forgot_password_never_uses_sms(self):
        with patch("communications.sms_provider.send") as sms_send:
            response = self.request_reset()
        self.assertEqual(response.status_code, 202)
        sms_send.assert_not_called()
        self.send_email.assert_called_once()

    def test_unknown_and_inactive_accounts_have_non_enumerating_responses(self):
        self.doctor.is_active = False
        self.doctor.save(update_fields=["is_active"])
        for email in ("missing@example.com", self.doctor.email):
            with self.subTest(email=email):
                response = self.request_reset(email)
                self.assertEqual(response.status_code, 202, response.content)
                data = response.json()
                self.assertTrue(data["verification_required"])
                self.assertTrue(data["reset_token"])
                self.assertNotIn("does not exist", response.content.decode().lower())
                self.assertNotIn("disabled", response.content.decode().lower())
        self.send_email.assert_not_called()
        self.assertFalse(PasswordResetVerification.objects.filter(user=self.doctor).exists())

    def test_request_requires_valid_email_and_csrf(self):
        for email in ("not-an-email", "", "patient@gmail.com\nBcc: attacker@example.com"):
            with self.subTest(email=email):
                response = self.request_reset(email)
                self.assertEqual(response.status_code, 400)
        self.send_email.assert_not_called()
        untrusted = Client(enforce_csrf_checks=True)
        response = untrusted.post(
            "/api/password-reset/request",
            data=json.dumps({"email": self.patient.email}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_provider_failure_returns_safe_error_without_usable_challenge(self):
        self.send_email.side_effect = PasswordResetEmailError("provider rejected")
        response = self.request_reset()
        self.assertEqual(response.status_code, 503, response.content)
        self.assertNotIn("reset_token", response.json())
        self.assertNotIn("provider rejected", response.content.decode())
        self.assertFalse(
            PasswordResetVerification.objects.filter(user=self.patient, is_used=False).exists()
        )

    def test_resend_transport_posts_html_and_text_to_registered_email(self):
        provider_response = MagicMock()
        provider_response.status = 200
        provider_response.read.return_value = b'{"id":"email_test_123"}'
        provider_response.__enter__.return_value = provider_response
        with patch("accounts.password_reset.urlopen", return_value=provider_response) as open_url:
            send_password_reset_email(self.patient.email, "123456")

        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.resend.com/emails")
        self.assertEqual(request.get_method(), "POST")
        headers = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(headers["authorization"], "Bearer re_test_password_reset")
        self.assertEqual(headers["content-type"], "application/json")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["from"], "BORJA Dental Clinic <noreply@borjadental.example>")
        self.assertEqual(payload["to"], [self.patient.email])
        self.assertIn("Password Reset Verification Code", payload["subject"])
        self.assertIn("123456", payload["html"])
        self.assertIn("123456", payload["text"])
        self.assertIn("5 minutes", payload["html"])
        self.assertIn("5 minutes", payload["text"])
        self.assertNotIn("http", payload["text"].lower())

    def test_resend_transport_handles_http_rejection_without_leaking_secrets(self):
        rejection = HTTPError(
            "https://api.resend.com/emails", 403, "rejected", None, None
        )
        with patch("accounts.password_reset.urlopen", side_effect=rejection):
            with self.assertRaises(PasswordResetEmailError) as error:
                send_password_reset_email(self.patient.email, "123456")
        self.assertNotIn("123456", str(error.exception))
        self.assertNotIn("re_test_password_reset", str(error.exception))

    @override_settings(RESEND_API_KEY="", RESEND_FROM_EMAIL="")
    def test_missing_resend_configuration_fails_safely(self):
        response = self.request_reset()
        self.assertEqual(response.status_code, 503, response.content)
        self.assertNotIn("reset_token", response.json())
        self.send_email.assert_not_called()

    def test_exact_six_digit_code_required_and_malformed_codes_count_toward_limit(self):
        token, code = self.requested_token_and_code()
        for invalid in ("", "12345", "1234567", "a12345", "123 45"):
            with self.subTest(code=invalid):
                response = self.post(
                    "/api/password-reset/verify",
                    {"reset_token": token, "code": invalid},
                )
                self.assertIn(response.status_code, (400, 429))
        challenge = PasswordResetVerification.objects.get(user=self.patient)
        self.assertEqual(challenge.attempts, 5)
        self.assertNotEqual(
            self.post("/api/password-reset/verify", {"reset_token": token, "code": code}).status_code,
            200,
        )

    def test_five_wrong_six_digit_codes_block_the_correct_code(self):
        token, code = self.requested_token_and_code()
        wrong = "999999" if code != "999999" else "111111"
        for attempt in range(5):
            response = self.post(
                "/api/password-reset/verify", {"reset_token": token, "code": wrong}
            )
            self.assertIn(response.status_code, (400, 429))
        challenge = PasswordResetVerification.objects.get(user=self.patient)
        self.assertEqual(challenge.attempts, 5)
        self.assertNotEqual(
            self.post("/api/password-reset/verify", {"reset_token": token, "code": code}).status_code,
            200,
        )

    def test_correct_code_verifies_once_without_changing_password(self):
        token, code = self.requested_token_and_code()
        response = self.post(
            "/api/password-reset/verify", {"reset_token": token, "code": code}
        )
        self.assertEqual(response.status_code, 200, response.content)
        challenge = PasswordResetVerification.objects.get(user=self.patient)
        self.assertTrue(challenge.is_verified)
        self.assertIsNotNone(challenge.verified_at)
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.check_password("OldPatient123!"))
        repeated = self.post(
            "/api/password-reset/verify", {"reset_token": token, "code": code}
        )
        self.assertNotEqual(repeated.status_code, 200)

    def test_expired_and_invalid_tokens_cannot_be_verified(self):
        token, code = self.requested_token_and_code()
        self.assertEqual(
            self.post(
                "/api/password-reset/verify",
                {"reset_token": "a" * 43, "code": code},
            ).status_code,
            400,
        )
        PasswordResetVerification.objects.filter(user=self.patient).update(
            expires_at=timezone.now() - dt.timedelta(seconds=1)
        )
        self.assertEqual(
            self.post(
                "/api/password-reset/verify", {"reset_token": token, "code": code}
            ).status_code,
            410,
        )

    def test_otp_with_surrounding_spaces_is_not_accepted(self):
        token, code = self.requested_token_and_code()
        spaced = self.post(
            "/api/password-reset/verify", {"reset_token": token, "code": f" {code} "}
        )
        self.assertEqual(spaced.status_code, 400)
        self.assertEqual(PasswordResetVerification.objects.get(user=self.patient).attempts, 1)
        self.assertEqual(
            self.post("/api/password-reset/verify", {"reset_token": token, "code": code}).status_code,
            200,
        )

    def test_request_cooldown_and_resend_cooldown(self):
        token, _ = self.requested_token_and_code()
        self.assertEqual(self.request_reset().status_code, 429)
        self.assertEqual(
            self.post("/api/password-reset/resend", {"reset_token": token}).status_code,
            429,
        )
        self.assertEqual(self.send_email.call_count, 1)

    def test_resend_rotates_token_and_code_and_invalidates_previous(self):
        token, code = self.requested_token_and_code()
        PasswordResetVerification.objects.filter(user=self.patient).update(
            created_at=timezone.now() - dt.timedelta(seconds=61)
        )
        response = self.post("/api/password-reset/resend", {"reset_token": token})
        self.assertEqual(response.status_code, 202, response.content)
        new_token = response.json()["reset_token"]
        new_code = self.code_sent()
        self.assertNotEqual(new_token, token)
        self.assertNotEqual(new_code, code)
        self.assertEqual(self.send_email.call_count, 2)
        self.assertEqual(self.send_email.call_args.args[0], self.patient.email)
        self.assertNotEqual(
            self.post("/api/password-reset/verify", {"reset_token": token, "code": code}).status_code,
            200,
        )
        self.assertNotEqual(
            self.post("/api/password-reset/verify", {"reset_token": new_token, "code": code}).status_code,
            200,
        )
        self.assertEqual(
            self.post("/api/password-reset/verify", {"reset_token": new_token, "code": new_code}).status_code,
            200,
        )

    def test_resend_changes_code_even_if_random_draw_collides(self):
        with patch("accounts.password_reset.secrets.randbelow", return_value=123456):
            token, first_code = self.requested_token_and_code()
            PasswordResetVerification.objects.filter(user=self.patient).update(
                created_at=timezone.now() - dt.timedelta(seconds=61)
            )
            response = self.post("/api/password-reset/resend", {"reset_token": token})
        self.assertEqual(response.status_code, 202, response.content)
        self.assertEqual(first_code, "123456")
        self.assertEqual(self.code_sent(), "123457")

    def test_expired_challenge_cannot_be_resent(self):
        token, _ = self.requested_token_and_code()
        PasswordResetVerification.objects.filter(user=self.patient).update(
            created_at=timezone.now() - dt.timedelta(minutes=6),
            expires_at=timezone.now() - dt.timedelta(minutes=1),
        )
        response = self.post("/api/password-reset/resend", {"reset_token": token})
        self.assertEqual(response.status_code, 410)
        self.assertEqual(self.send_email.call_count, 1)

    def test_hourly_email_limit_stops_repeated_requests(self):
        token, _ = self.requested_token_and_code()
        limited = None
        for attempt in range(10):
            PasswordResetVerification.objects.filter(user=self.patient, is_used=False).update(
                created_at=timezone.now() - dt.timedelta(seconds=61)
            )
            # Rotate the client address so this specifically exercises the
            # database-backed email limit, not only the per-address cache limit.
            client = Client(enforce_csrf_checks=True, REMOTE_ADDR=f"10.0.0.{attempt + 1}")
            csrf = client.get("/api/session").json()["csrf_token"]
            response = self.post(
                "/api/password-reset/resend",
                {"reset_token": token},
                client=client,
                csrf=csrf,
            )
            if response.status_code == 429:
                limited = response
                break
            self.assertEqual(response.status_code, 202, response.content)
            token = response.json()["reset_token"]
        self.assertIsNotNone(limited, "Hourly reset email attempts must be bounded")
        self.assertLessEqual(self.send_email.call_count, 10)

    def test_confirm_rejects_unverified_expired_and_invalid_tokens(self):
        token, _ = self.requested_token_and_code()
        self.assertEqual(self.confirm(token).status_code, 400)
        self.assertEqual(self.confirm("a" * 43).status_code, 400)
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.check_password("OldPatient123!"))

        verified = self.verified_token(self.doctor.email)
        PasswordResetVerification.objects.filter(user=self.doctor).update(
            expires_at=timezone.now() - dt.timedelta(seconds=1)
        )
        self.assertEqual(self.confirm(verified, "NewDoctor456!").status_code, 410)

    def test_confirm_requires_matching_strong_password_and_preserves_challenge(self):
        token = self.verified_token()
        mismatch = self.post(
            "/api/password-reset/confirm",
            {
                "reset_token": token,
                "new_password": "NewPatient456!",
                "confirm_password": "OtherPatient456!",
            },
        )
        self.assertEqual(mismatch.status_code, 400)
        for password in ("short", "lowercase123!", "UPPERCASE123!", "MixedCase123"):
            with self.subTest(password=password):
                response = self.confirm(token, password)
                self.assertEqual(response.status_code, 400, response.content)
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.check_password("OldPatient123!"))
        self.assertFalse(PasswordResetVerification.objects.get(user=self.patient).is_used)
        self.assertEqual(self.confirm(token).status_code, 200)

    def test_success_changes_only_target_password_and_revokes_old_sessions(self):
        first_session = self.login_as(self.patient, "OldPatient123!")
        second_session = self.login_as(self.patient, "OldPatient123!")
        doctor_session = self.login_as(self.doctor, "OldDoctor123!")
        AccountAuthState.objects.create(
            user=self.patient,
            failed_attempts=5,
            last_failed_at=timezone.now(),
            locked_until=timezone.now() + dt.timedelta(minutes=15),
        )
        token = self.verified_token()
        response = self.post(
            "/api/password-reset/confirm",
            {
                "reset_token": token,
                "new_password": "NewPatient456!",
                "confirm_password": "NewPatient456!",
                "email": self.doctor.email,
                "user_id": self.doctor.pk,
                "otp_verified": True,
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {"ok": True})
        self.assertNotIn("NewPatient456!", response.content.decode())
        self.patient.refresh_from_db()
        self.doctor.refresh_from_db()
        self.assertNotEqual(self.patient.password, "NewPatient456!")
        self.assertTrue(self.patient.check_password("NewPatient456!"))
        self.assertFalse(self.patient.check_password("OldPatient123!"))
        self.assertTrue(self.doctor.check_password("OldDoctor123!"))
        self.assertIsNone(first_session.get("/api/session").json()["user"])
        self.assertIsNone(second_session.get("/api/session").json()["user"])
        self.assertEqual(doctor_session.get("/api/session").json()["user"]["id"], self.doctor.pk)
        state = AccountAuthState.objects.get(user=self.patient)
        self.assertEqual(state.failed_attempts, 0)
        self.assertIsNone(state.locked_until)
        challenge = PasswordResetVerification.objects.get(user=self.patient)
        self.assertTrue(challenge.is_used)
        self.assertIsNotNone(challenge.used_at)
        self.assertNotEqual(self.confirm(token).status_code, 200)
        audit = AuditEvent.objects.get(target_id=self.patient.pk, event="PASSWORD_RESET")
        self.assertIsNone(audit.actor)
        self.assertEqual(audit.metadata, {"channel": "email"})

        new_session = self.login_as(self.patient, "NewPatient456!")
        self.assertEqual(new_session.get("/api/session").json()["user"]["id"], self.patient.pk)
        old_session = Client(enforce_csrf_checks=True)
        old_csrf = old_session.get("/api/session").json()["csrf_token"]
        old_login = self.post(
            "/api/login",
            {"email": self.patient.email, "password": "OldPatient123!"},
            client=old_session,
            csrf=old_csrf,
        )
        self.assertEqual(old_login.status_code, 401)

    def test_normal_password_change_revokes_verified_reset_challenge(self):
        account_session = self.login_as(self.patient, "OldPatient123!")
        token = self.verified_token()
        csrf = account_session.get("/api/session").json()["csrf_token"]
        changed = self.post(
            "/api/account/change-password",
            {
                "current_password": "OldPatient123!",
                "new_password": "CurrentPatient789!",
                "confirm_password": "CurrentPatient789!",
            },
            client=account_session,
            csrf=csrf,
        )
        self.assertEqual(changed.status_code, 200, changed.content)
        self.assertEqual(self.confirm(token).status_code, 409)
        challenge = PasswordResetVerification.objects.get(user=self.patient)
        self.assertTrue(challenge.is_used)
        self.assertEqual(challenge.code_hash, "")
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.check_password("CurrentPatient789!"))

    def test_account_cannot_reset_with_another_users_token(self):
        token = self.verified_token()
        response = self.post(
            "/api/password-reset/confirm",
            {
                "reset_token": token,
                "new_password": "NewPatient456!",
                "confirm_password": "NewPatient456!",
                "email": self.doctor.email,
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.doctor.refresh_from_db()
        self.assertTrue(self.doctor.check_password("OldDoctor123!"))
        self.assertFalse(self.doctor.check_password("NewPatient456!"))
