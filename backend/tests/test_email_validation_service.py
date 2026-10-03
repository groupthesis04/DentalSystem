"""Email Reputation requests are mocked and never consume Abstract API credits."""

import io
import json
import os
from http.client import IncompleteRead
from unittest import mock
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

from django.core.cache import cache
from django.test import SimpleTestCase

from accounts.email_validation import validate_email_address


class EmailValidationServiceTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        key = mock.patch.dict(os.environ, {"ABSTRACT_EMAIL_REPUTATION_API_KEY": "test-secret"})
        key.start()
        self.addCleanup(key.stop)

    def provider_result(self, **overrides):
        response = {
            "email_address": "patient@example.com",
            "email_deliverability": {
                "status": "deliverable",
                "status_detail": "valid_email",
                "is_format_valid": True,
                "is_smtp_valid": True,
                "is_mx_valid": True,
            },
            "email_quality": {"is_disposable": False, "is_catchall": False},
        }
        response.update(overrides)
        return response

    def with_deliverability(self, **overrides):
        data = self.provider_result()
        data["email_deliverability"].update(overrides)
        return data

    def with_quality(self, **overrides):
        data = self.provider_result()
        data["email_quality"].update(overrides)
        return data

    def mock_response(self, payload):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        return mock.patch("accounts.email_validation.urlopen", side_effect=lambda *args, **kwargs: io.BytesIO(body))

    def test_valid_email_uses_email_reputation_endpoint_and_nested_response(self):
        with self.mock_response(self.provider_result()) as request:
            result = validate_email_address("  Patient@Example.COM  ")

        self.assertEqual(result, {
            "valid": True,
            "status": "valid",
            "message": "Email address is valid.",
        })
        self.assertEqual(request.call_count, 1)
        url = urlsplit(request.call_args.args[0].full_url)
        self.assertEqual(f"{url.scheme}://{url.netloc}{url.path}", "https://emailreputation.abstractapi.com/v1")
        self.assertEqual(parse_qs(url.query), {"email": ["patient@example.com"]})
        self.assertNotIn("test-secret", request.call_args.args[0].full_url)
        self.assertEqual(request.call_args.args[0].get_header("Authorization"), "Bearer test-secret")
        self.assertGreater(request.call_args.kwargs["timeout"], 0)
        self.assertLessEqual(request.call_args.kwargs["timeout"], 15)

    def test_invalid_local_syntax_skips_provider(self):
        with mock.patch("accounts.email_validation.urlopen") as request:
            result = validate_email_address("patient@@example.com")

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["message"], "Please enter a valid email address.")
        request.assert_not_called()

    def test_valid_gmail_like_address(self):
        with self.mock_response(self.provider_result(email_address="patient@gmail.com")):
            result = validate_email_address("Patient@Gmail.Com")
        self.assertEqual(result["status"], "valid")
        self.assertTrue(result["valid"])

    def test_explicitly_invalid_format_is_rejected(self):
        with self.mock_response(self.with_deliverability(is_format_valid=False)):
            result = validate_email_address("patient@example.com")
        self.assertEqual(result["status"], "invalid")
        self.assertFalse(result["valid"])

    def test_explicitly_invalid_mx_is_rejected(self):
        with self.mock_response(self.with_deliverability(is_mx_valid=False)):
            result = validate_email_address("patient@example.com")
        self.assertEqual(result["status"], "invalid")
        self.assertFalse(result["valid"])

    def test_undeliverable_is_rejected(self):
        with self.mock_response(self.with_deliverability(status="undeliverable", is_smtp_valid=False)):
            result = validate_email_address("patient@example.com")
        self.assertEqual(result["status"], "invalid")

    def test_disposable_email_is_rejected(self):
        with self.mock_response(self.with_quality(is_disposable=True)):
            result = validate_email_address("patient@example.com")
        self.assertEqual(result["status"], "disposable")
        self.assertEqual(result["message"], "Temporary or disposable email addresses are not allowed.")

    def test_catchall_or_unknown_is_not_called_undeliverable(self):
        cases = (
            self.with_deliverability(status="unknown", is_smtp_valid=None),
            self.provider_result(
                email_deliverability={"status": "unknown", "is_format_valid": True},
                email_quality={"is_disposable": False, "is_catchall": True},
            ),
        )
        for payload in cases:
            with self.subTest(payload=payload):
                cache.clear()
                with self.mock_response(payload):
                    result = validate_email_address("patient@example.com")
                self.assertEqual(result["status"], "unknown")
                self.assertFalse(result["valid"])
                self.assertEqual(
                    result["message"],
                    "This email address could not be fully verified. Please check the address or try another email.",
                )

    def test_missing_optional_flags_do_not_override_deliverable_status(self):
        with self.mock_response({
            "email_address": "patient@example.com",
            "email_deliverability": {"status": "deliverable"},
        }):
            result = validate_email_address("patient@example.com")
        self.assertEqual(result["status"], "valid")

    def test_catchall_does_not_override_explicit_deliverable_status(self):
        with self.mock_response(self.with_quality(is_catchall=True)):
            result = validate_email_address("patient@example.com")
        self.assertEqual(result["status"], "valid")

    def test_deliverable_with_explicit_smtp_failure_is_uncertain(self):
        with self.mock_response(self.with_deliverability(is_smtp_valid=False)):
            result = validate_email_address("patient@example.com")
        self.assertEqual(result["status"], "unknown")

    def test_safe_domain_suggestion_does_not_rewrite_rejected_address(self):
        response = self.with_deliverability(status="undeliverable", is_mx_valid=False)
        response["email_address"] = "patient@gmial.com"
        response["suggested_correction"] = "patient@gmail.com"
        with self.mock_response(response):
            result = validate_email_address("patient@gmial.com")
        self.assertEqual(result["status"], "invalid")
        self.assertFalse(result["valid"])
        self.assertEqual(result["suggested_email"], "patient@gmail.com")

    def test_suggestion_for_another_mailbox_is_ignored(self):
        response = self.with_deliverability(status="undeliverable")
        response["suggested_correction"] = "someone-else@gmail.com"
        with self.mock_response(response):
            result = validate_email_address("patient@example.com")
        self.assertEqual(result["status"], "invalid")
        self.assertNotIn("suggested_email", result)

    def test_missing_or_malformed_response_fields_never_crash_or_claim_valid(self):
        payloads = (
            [],
            {"email_address": "patient@example.com"},
            {"email_deliverability": [], "email_quality": "wrong-type"},
            {"email_address": "someone-else@example.com", "email_deliverability": {"status": "deliverable"}},
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                cache.clear()
                with self.mock_response(payload):
                    result = validate_email_address("patient@example.com")
                self.assertFalse(result["valid"])
                self.assertIn(result["status"], {"unknown", "service_unavailable"})

    def test_timeout_and_dns_failure_are_temporary_errors(self):
        for error in (
            TimeoutError("test-secret in URL"),
            URLError("test-secret in URL"),
            IncompleteRead(b"", 1),
        ):
            with self.subTest(error=type(error).__name__):
                cache.clear()
                with mock.patch("accounts.email_validation.urlopen", side_effect=error):
                    with self.assertLogs("accounts.email_validation", level="WARNING") as logs:
                        result = validate_email_address("patient@example.com")
                self.assertEqual(result["status"], "service_unavailable")
                self.assertNotIn("test-secret", str(result))
                self.assertNotIn("test-secret", " ".join(logs.output))

    def test_http_errors_are_temporary_and_never_expose_key(self):
        for status in (400, 401, 403, 404, 429, 500, 503):
            with self.subTest(status=status):
                cache.clear()
                error = HTTPError(
                    "https://emailreputation.abstractapi.com/v1?email=patient%40example.com",
                    status, "provider failure test-secret", None, io.BytesIO(b"test-secret provider body"),
                )
                with mock.patch("accounts.email_validation.urlopen", side_effect=error):
                    with self.assertLogs("accounts.email_validation", level="WARNING") as logs:
                        result = validate_email_address("patient@example.com")
                self.assertEqual(result["status"], "service_unavailable")
                self.assertNotIn("test-secret", str(result))
                self.assertNotIn("test-secret", " ".join(logs.output))

    def test_malformed_or_unusable_response_is_temporary_error(self):
        with self.mock_response(b"not-json"):
            with self.assertLogs("accounts.email_validation", level="WARNING"):
                result = validate_email_address("patient@example.com")
        self.assertEqual(result["status"], "service_unavailable")

    def test_missing_key_does_not_call_provider(self):
        with mock.patch.dict(os.environ, {"ABSTRACT_EMAIL_REPUTATION_API_KEY": ""}):
            with mock.patch("accounts.email_validation.urlopen") as request:
                with self.assertLogs("accounts.email_validation", level="WARNING"):
                    result = validate_email_address("patient@example.com")
        self.assertEqual(result["status"], "service_unavailable")
        request.assert_not_called()

    def test_normalized_email_is_cached_but_changing_key_bypasses_cache(self):
        with self.mock_response(self.provider_result()) as request:
            first = validate_email_address("  PATIENT@example.com ")
            second = validate_email_address("patient@example.com")
            with mock.patch.dict(os.environ, {"ABSTRACT_EMAIL_REPUTATION_API_KEY": "new-test-secret"}):
                third = validate_email_address("patient@example.com")

        self.assertEqual(first, second)
        self.assertEqual(third["status"], "valid")
        self.assertEqual(request.call_count, 2)
        self.assertNotIn("test-secret", str(first))

