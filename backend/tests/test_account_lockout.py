"""Password sign-in and database-backed account lockout regression tests."""

import datetime as dt

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from accounts.audit_models import AuditEvent
from accounts.models import AccountAuthState, AccountLoginActivity, User


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AccountLockoutTests(TestCase):
    def setUp(self):
        cache.clear()
        self.doctor = User.objects.create_user(
            email="doctor@example.com", password="Doctor123!", name="Dr. Test",
            role="doctor", is_staff=True,
        )
        self.patient = User.objects.create_user(
            email="patient@example.com", password="Patient123!", name="Patient Test",
            role="patient",
        )

    def client_with_csrf(self, address="127.0.0.1"):
        client = Client(enforce_csrf_checks=True, REMOTE_ADDR=address)
        token = client.get("/api/session").json()["csrf_token"]
        return client, token

    def login(self, client, token, user=None, password="Doctor123!"):
        account = user or self.doctor
        return client.post(
            "/api/login",
            data={"email": account.email, "password": password},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

    def test_doctor_password_login_creates_session_and_activity(self):
        client, token = self.client_with_csrf()
        response = self.login(client, token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["id"], self.doctor.pk)
        self.assertIn("csrf_token", response.json())
        self.assertNotIn("mfa_required", response.json())
        self.assertNotIn("mfa_setup_required", response.json())
        self.assertEqual(client.get("/api/session").json()["user"]["id"], self.doctor.pk)
        self.assertEqual(AccountLoginActivity.objects.filter(user=self.doctor).count(), 1)
        self.assertEqual(AuditEvent.objects.filter(event="LOGIN_SUCCESS", actor=self.doctor).count(), 1)

    def test_five_bad_passwords_across_addresses_lock_account_for_fifteen_minutes(self):
        for attempt in range(5):
            client, token = self.client_with_csrf(f"127.0.0.{attempt + 1}")
            response = self.login(client, token, password="wrong-password")
            self.assertEqual(response.status_code, 429 if attempt == 4 else 401)
            self.assertIsNone(client.get("/api/session").json()["user"])

        state = AccountAuthState.objects.get(user=self.doctor)
        self.assertEqual(state.failed_attempts, 5)
        self.assertGreater(state.locked_until, timezone.now())
        self.assertLessEqual(state.locked_until, timezone.now() + dt.timedelta(minutes=15))
        self.assertEqual(AuditEvent.objects.filter(event="ACCOUNT_LOCKED", target_id=self.doctor.pk).count(), 1)
        self.assertEqual(AuditEvent.objects.filter(event="LOGIN_FAILED", target_id=self.doctor.pk).count(), 5)

        client, token = self.client_with_csrf("127.0.0.9")
        self.assertEqual(self.login(client, token).status_code, 429)
        self.assertIsNone(client.get("/api/session").json()["user"])

        state.locked_until = timezone.now() - dt.timedelta(seconds=1)
        state.last_failed_at = timezone.now() - dt.timedelta(minutes=16)
        state.save(update_fields=["locked_until", "last_failed_at"])
        self.assertEqual(self.login(client, token).status_code, 200)
        state.refresh_from_db()
        self.assertEqual(state.failed_attempts, 0)
        self.assertIsNone(state.locked_until)
        self.assertIsNone(state.last_failed_at)
        self.assertEqual(client.get("/api/session").json()["user"]["id"], self.doctor.pk)

    def test_successful_login_clears_recent_failures_for_doctor_and_patient(self):
        for user, correct_password, address in (
            (self.doctor, "Doctor123!", "127.0.1.1"),
            (self.patient, "Patient123!", "127.0.1.2"),
        ):
            with self.subTest(role=user.role):
                client, token = self.client_with_csrf(address)
                self.assertEqual(self.login(client, token, user, "wrong").status_code, 401)
                self.assertEqual(AccountAuthState.objects.get(user=user).failed_attempts, 1)
                response = self.login(client, token, user, correct_password)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["user"]["id"], user.pk)
                state = AccountAuthState.objects.get(user=user)
                self.assertEqual(state.failed_attempts, 0)
                self.assertIsNone(state.last_failed_at)
                self.assertIsNone(state.locked_until)

    def test_patient_is_subject_to_account_lockout(self):
        for attempt in range(5):
            client, token = self.client_with_csrf(f"127.0.2.{attempt + 1}")
            response = self.login(client, token, self.patient, "wrong")
            self.assertEqual(response.status_code, 429 if attempt == 4 else 401)
        self.assertEqual(AccountAuthState.objects.get(user=self.patient).failed_attempts, 5)
        client, token = self.client_with_csrf("127.0.2.9")
        self.assertEqual(self.login(client, token, self.patient, "Patient123!").status_code, 429)
        self.assertIsNone(client.get("/api/session").json()["user"])

    def test_disabled_account_message_requires_correct_password(self):
        self.doctor.is_active = False
        self.doctor.save(update_fields=["is_active"])
        client, token = self.client_with_csrf()
        self.assertEqual(self.login(client, token, password="wrong").status_code, 401)
        correct = self.login(client, token)
        self.assertEqual(correct.status_code, 403)
        self.assertIn("disabled", correct.json()["error"])
        self.assertIsNone(client.get("/api/session").json()["user"])

        for attempt in range(4):
            other, other_token = self.client_with_csrf(f"127.0.3.{attempt + 1}")
            response = self.login(other, other_token, password="wrong")
            self.assertEqual(response.status_code, 429 if attempt == 3 else 401)
        self.assertEqual(AccountAuthState.objects.get(user=self.doctor).failed_attempts, 5)
        self.assertEqual(AuditEvent.objects.filter(event="ACCOUNT_LOCKED", target_id=self.doctor.pk).count(), 1)
        locked, locked_token = self.client_with_csrf("127.0.3.9")
        self.assertEqual(self.login(locked, locked_token).status_code, 429)
