"""Self-service account security, login history, and session revocation."""

from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from accounts.models import AccountLoginActivity, User


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AccountSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.doctor = User.objects.create_user(
            email="doctor@example.com",
            password="Doctor123!",
            name="Dr. Maria Santos",
            phone="09170002026",
            role="doctor",
            is_staff=True,
        )
        self.patient = User.objects.create_user(
            email="patient@example.com",
            password="Patient123!",
            name="Patient Example",
            role="patient",
        )

    def login(self, user=None, user_agent="Mozilla/5.0 (Windows NT 10.0) Chrome/120.0"):
        account = user or self.doctor
        client = Client(enforce_csrf_checks=True)
        token = client.get("/api/session").json()["csrf_token"]
        response = client.post(
            "/api/login",
            data={"email": account.email, "password": "Doctor123!" if account == self.doctor else "Patient123!"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
            HTTP_USER_AGENT=user_agent,
        )
        self.assertEqual(response.status_code, 200)
        return client, response.json()["csrf_token"]

    def post(self, client, token, path, payload=None):
        return client.post(path, data=payload or {}, content_type="application/json", HTTP_X_CSRFTOKEN=token)

    def patch(self, client, token, path, payload):
        return client.patch(path, data=payload, content_type="application/json", HTTP_X_CSRFTOKEN=token)

    def test_security_shows_real_status_last_login_and_recorded_device(self):
        client, _ = self.login()
        self.doctor.refresh_from_db()
        response = client.get("/api/account/security")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_active"])
        self.assertEqual(data["last_login"], self.doctor.last_login.isoformat())
        self.assertEqual(data["recovery_email"], self.doctor.email)
        self.assertEqual(data["recovery_mobile_number"], self.doctor.phone)
        self.assertEqual(data["other_sessions_count"], 0)
        self.assertEqual(len(data["login_activity"]), 1)
        self.assertEqual(data["login_activity"][0]["device"], "Windows · Chrome")
        self.assertTrue(data["login_activity"][0]["is_current"])
        self.assertNotIn("location", data["login_activity"][0])
        self.assertEqual(AccountLoginActivity.objects.filter(user=self.doctor).count(), 1)

    def test_logout_other_devices_revokes_only_this_doctors_other_sessions(self):
        first, first_token = self.login()
        second, _ = self.login(user_agent="Mozilla/5.0 (Linux; Android 15) Chrome/120.0")
        patient_client, _ = self.login(user=self.patient)

        before = first.get("/api/account/security").json()
        self.assertEqual(before["other_sessions_count"], 1)
        self.assertEqual(len(before["login_activity"]), 2)
        response = self.post(first, first_token, "/api/account/logout-other-devices")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["revoked_count"], 1)
        self.assertEqual(first.get("/api/session").json()["user"]["id"], self.doctor.id)
        self.assertIsNone(second.get("/api/session").json()["user"])
        self.assertEqual(patient_client.get("/api/session").json()["user"]["id"], self.patient.id)
        self.assertEqual(first.get("/api/account/security").json()["other_sessions_count"], 0)

    def test_change_password_checks_current_password_and_keeps_current_session(self):
        client, token = self.login()
        other, _ = self.login()
        endpoint = "/api/account/change-password"
        wrong = self.post(client, token, endpoint, {
            "current_password": "Wrong123!", "new_password": "NewDoctor456!", "confirm_password": "NewDoctor456!",
        })
        self.assertEqual(wrong.status_code, 400)
        mismatch = self.post(client, token, endpoint, {
            "current_password": "Doctor123!", "new_password": "NewDoctor456!", "confirm_password": "NoMatch456!",
        })
        self.assertEqual(mismatch.status_code, 400)
        changed = self.post(client, token, endpoint, {
            "current_password": "Doctor123!", "new_password": "NewDoctor456!", "confirm_password": "NewDoctor456!",
        })
        self.assertEqual(changed.status_code, 200)
        self.doctor.refresh_from_db()
        self.assertTrue(self.doctor.check_password("NewDoctor456!"))
        self.assertEqual(client.get("/api/session").json()["user"]["id"], self.doctor.id)
        self.assertIsNone(other.get("/api/session").json()["user"])
        self.assertTrue(any(
            entry["is_current"]
            for entry in client.get("/api/account/security").json()["login_activity"]
        ))

    def test_recovery_contacts_require_password_and_leave_primary_contacts_unchanged(self):
        client, token = self.login()
        endpoint = "/api/account/recovery-contact"
        wrong = self.patch(client, token, endpoint, {
            "email": "recovery@example.com", "mobile_number": "+639171112222", "current_password": "wrong",
        })
        self.assertEqual(wrong.status_code, 400)
        invalid = self.patch(client, token, endpoint, {
            "email": "recovery@example.com", "mobile_number": "123", "current_password": "Doctor123!",
        })
        self.assertEqual(invalid.status_code, 400)
        saved = self.patch(client, token, endpoint, {
            "email": "recovery@example.com", "mobile_number": "+639171112222", "current_password": "Doctor123!",
        })
        self.assertEqual(saved.status_code, 200)
        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.email, "doctor@example.com")
        self.assertEqual(self.doctor.phone, "09170002026")
        self.assertEqual(self.doctor.recovery_email, "recovery@example.com")
        self.assertEqual(self.doctor.recovery_mobile_number, "+639171112222")
        data = client.get("/api/account/security").json()
        self.assertEqual(data["recovery_email"], "recovery@example.com")
        self.assertEqual(data["recovery_mobile_number"], "+639171112222")

    def test_password_change_enforces_displayed_complexity_rules(self):
        client, token = self.login()
        endpoint = "/api/account/change-password"
        for candidate in ("lowercase123!", "UPPERCASE123!", "MixedCase123"):
            response = self.post(client, token, endpoint, {
                "current_password": "Doctor123!",
                "new_password": candidate,
                "confirm_password": candidate,
            })
            self.assertEqual(response.status_code, 400, candidate)
        self.doctor.refresh_from_db()
        self.assertTrue(self.doctor.check_password("Doctor123!"))

    def test_patient_security_shows_only_own_login_activity(self):
        self.login()
        patient_client, _ = self.login(user=self.patient, user_agent="Mozilla/5.0 (Linux; Android 15) Chrome/120.0")
        self.patient.refresh_from_db()

        response = patient_client.get("/api/account/security")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_active"])
        self.assertEqual(data["last_login"], self.patient.last_login.isoformat())
        self.assertEqual(data["recovery_email"], self.patient.email)
        self.assertEqual(data["other_sessions_count"], 0)
        self.assertEqual(len(data["login_activity"]), 1)
        self.assertEqual(data["login_activity"][0]["device"], "Android · Chrome")
        self.assertTrue(data["login_activity"][0]["is_current"])
        self.assertEqual(AccountLoginActivity.objects.filter(user=self.patient).count(), 1)
        self.assertEqual(patient_client.get("/api/account/activity-log").status_code, 403)

    def test_patient_can_change_own_password_and_other_patient_session_expires(self):
        patient_client, patient_token = self.login(user=self.patient)
        other_patient_client, _ = self.login(user=self.patient)
        doctor_client, _ = self.login()
        endpoint = "/api/account/change-password"
        payload = {
            "current_password": "Patient123!",
            "new_password": "NewPatient456!",
            "confirm_password": "NewPatient456!",
        }

        self.assertEqual(self.post(patient_client, patient_token, endpoint, {
            **payload, "current_password": "incorrect",
        }).status_code, 400)
        self.assertEqual(self.post(patient_client, patient_token, endpoint, {
            **payload, "confirm_password": "Different456!",
        }).status_code, 400)
        response = self.post(patient_client, patient_token, endpoint, payload)
        self.assertEqual(response.status_code, 200)
        self.patient.refresh_from_db()
        self.doctor.refresh_from_db()
        self.assertTrue(self.patient.check_password("NewPatient456!"))
        self.assertTrue(self.doctor.check_password("Doctor123!"))
        self.assertEqual(patient_client.get("/api/session").json()["user"]["id"], self.patient.id)
        self.assertIsNone(other_patient_client.get("/api/session").json()["user"])
        self.assertEqual(doctor_client.get("/api/session").json()["user"]["id"], self.doctor.id)
        self.assertTrue(any(
            entry["is_current"]
            for entry in patient_client.get("/api/account/security").json()["login_activity"]
        ))

    def test_patient_can_update_own_recovery_contact_with_password(self):
        patient_client, patient_token = self.login(user=self.patient)
        endpoint = "/api/account/recovery-contact"
        payload = {
            "email": "patient-recovery@example.com",
            "mobile_number": "+639171112222",
            "current_password": "Patient123!",
        }
        self.assertEqual(self.patch(patient_client, patient_token, endpoint, {
            **payload, "current_password": "incorrect",
        }).status_code, 400)
        response = self.patch(patient_client, patient_token, endpoint, payload)
        self.assertEqual(response.status_code, 200)
        self.patient.refresh_from_db()
        self.doctor.refresh_from_db()
        self.assertEqual(self.patient.recovery_email, payload["email"])
        self.assertEqual(self.patient.recovery_mobile_number, payload["mobile_number"])
        self.assertEqual(self.patient.email, "patient@example.com")
        self.assertEqual(self.doctor.recovery_email, "")

    def test_patient_logout_other_devices_preserves_doctor_sessions(self):
        patient_client, patient_token = self.login(user=self.patient)
        other_patient_client, _ = self.login(user=self.patient)
        doctor_client, _ = self.login()
        self.assertEqual(patient_client.get("/api/account/security").json()["other_sessions_count"], 1)

        response = self.post(patient_client, patient_token, "/api/account/logout-other-devices")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["revoked_count"], 1)
        self.assertEqual(patient_client.get("/api/session").json()["user"]["id"], self.patient.id)
        self.assertIsNone(other_patient_client.get("/api/session").json()["user"])
        self.assertEqual(doctor_client.get("/api/session").json()["user"]["id"], self.doctor.id)
        self.assertEqual(patient_client.get("/api/account/security").json()["other_sessions_count"], 0)

    def test_security_controls_require_login_and_csrf(self):
        anonymous = Client()
        self.assertEqual(anonymous.get("/api/account/security").status_code, 401)
        self.assertEqual(self.post(anonymous, "", "/api/account/change-password").status_code, 401)
        self.assertEqual(self.patch(anonymous, "", "/api/account/recovery-contact", {}).status_code, 401)
        self.assertEqual(self.post(anonymous, "", "/api/account/logout-other-devices").status_code, 401)

        for account in (self.doctor, self.patient):
            client, _ = self.login(user=account)
            self.assertEqual(client.post(
                "/api/account/change-password", data={}, content_type="application/json",
            ).status_code, 403)
            self.assertEqual(client.patch(
                "/api/account/recovery-contact", data={}, content_type="application/json",
            ).status_code, 403)
            self.assertEqual(client.post(
                "/api/account/logout-other-devices", data={}, content_type="application/json",
            ).status_code, 403)
