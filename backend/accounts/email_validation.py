"""Server-side email deliverability checks for patient registration.

Only this module talks to Abstract. Its public result contains patient-safe
messages, never provider responses, request URLs, or credentials.
"""

import hashlib
import json
import logging
import os
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email as django_validate_email

from dental_backend.api import validate_email as local_validate_email


logger = logging.getLogger(__name__)

ABSTRACT_EMAIL_REPUTATION_URL = "https://emailreputation.abstractapi.com/v1"
REQUEST_TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 64 * 1024
RESULT_CACHE_SECONDS = 5 * 60
UNCERTAIN_CACHE_SECONDS = 60
FAILURE_CACHE_SECONDS = 20

_MESSAGES = {
    "valid": "Email address is valid.",
    "invalid": "This email address could not be verified. Please check the address and try again.",
    "invalid_format": "Please enter a valid email address.",
    "disposable": "Temporary or disposable email addresses are not allowed.",
    "unknown": "This email address could not be fully verified. Please check the address or try another email.",
    "service_unavailable": "Email validation is temporarily unavailable. Please try again.",
}


def _result(status, *, message=None, suggested_email=None):
    result = {
        "valid": status == "valid",
        "status": status,
        "message": message or _MESSAGES[status],
    }
    if suggested_email:
        result["suggested_email"] = suggested_email
    return result


def _normalize_email(value):
    if not isinstance(value, str):
        return None
    email = value.strip().lower()
    if len(email) > 254:
        return None
    try:
        email = local_validate_email(email)
        django_validate_email(email)
    except (ValueError, ValidationError):
        return None
    return email


def _boolean(value):
    # The Email Reputation API documents booleans, but tolerate string values
    # without interpreting numbers or arbitrary objects as true/false.
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.strip().lower() == "true":
            return True
        if value.strip().lower() == "false":
            return False
    return None


def _suggested_email(data, original):
    candidate = data.get("suggested_correction")
    if not isinstance(candidate, str):
        return None
    suggestion = _normalize_email(candidate)
    if not suggestion or suggestion == original:
        return None
    # The provider's suggestion is for a domain typo, not permission to
    # substitute another mailbox owner's local part.
    if suggestion.split("@", 1)[0] != original.split("@", 1)[0]:
        return None
    return suggestion


def _classify_response(data, email):
    if not isinstance(data, dict):
        logger.warning("Abstract Email Reputation API returned an unexpected response type")
        return _result("service_unavailable")

    provider_email = data.get("email_address")
    if provider_email is not None and (
        not isinstance(provider_email, str) or provider_email.strip().lower() != email
    ):
        logger.warning("Abstract Email Reputation API returned a mismatched address")
        return _result("service_unavailable")

    deliverability_data = data.get("email_deliverability") or {}
    quality_data = data.get("email_quality") or {}
    if not isinstance(deliverability_data, dict) or not isinstance(quality_data, dict):
        logger.warning("Abstract Email Reputation API returned malformed checks")
        return _result("service_unavailable")

    raw_status = deliverability_data.get("status")
    deliverability = raw_status.strip().lower() if isinstance(raw_status, str) else None
    if not deliverability:
        deliverability = None
    format_valid = _boolean(deliverability_data.get("is_format_valid"))
    mx_valid = _boolean(deliverability_data.get("is_mx_valid"))
    smtp_valid = _boolean(deliverability_data.get("is_smtp_valid"))
    disposable = _boolean(quality_data.get("is_disposable"))
    is_catchall = _boolean(quality_data.get("is_catchall"))

    if all(
        value is None
        for value in (deliverability, format_valid, mx_valid, smtp_valid, disposable, is_catchall)
    ):
        logger.warning("Abstract Email Reputation API returned no usable checks")
        return _result("service_unavailable")

    suggestion = _suggested_email(data, email)
    if disposable is True:
        return _result("disposable")

    if format_valid is False or mx_valid is False or deliverability == "undeliverable":
        return _result("invalid", suggested_email=suggestion)

    # An affirmative overall status is sufficient when an optional boolean is
    # absent. A catch-all flag alone is not grounds to override deliverable;
    # Abstract's documented example itself reports both at once.
    if deliverability == "deliverable" and smtp_valid is not False:
        return _result("valid", suggested_email=suggestion)

    return _result("unknown", suggested_email=suggestion)


def _cache_key(email, api_key):
    # Hash both values so cache keys contain neither patient data nor secrets.
    digest = hashlib.sha256(f"{api_key}\0{email}".encode("utf-8")).hexdigest()
    return f"drms-email-reputation:{digest}"


def _cached_result(cache_key):
    try:
        result = cache.get(cache_key)
    except Exception:
        logger.warning("Email reputation cache lookup failed")
        return None
    return dict(result) if isinstance(result, dict) else None


def _remember(cache_key, result):
    duration = {
        "unknown": UNCERTAIN_CACHE_SECONDS,
        "service_unavailable": FAILURE_CACHE_SECONDS,
    }.get(result["status"], RESULT_CACHE_SECONDS)
    try:
        cache.set(cache_key, dict(result), duration)
    except Exception:
        logger.warning("Email reputation cache write failed")
    return result


def validate_email_address(email):
    """Return a sanitized assessment; only ``valid=True`` permits signup."""
    normalized = _normalize_email(email)
    if not normalized:
        return _result("invalid", message=_MESSAGES["invalid_format"])

    api_key = os.environ.get("ABSTRACT_EMAIL_REPUTATION_API_KEY", "").strip()
    if not api_key:
        logger.warning("Abstract Email Reputation API is not configured")
        return _result("service_unavailable")

    cache_key = _cache_key(normalized, api_key)
    cached = _cached_result(cache_key)
    if cached is not None:
        return cached

    # Header authentication is documented by Abstract and keeps the secret out
    # of URLs that can be recorded by proxies, exception text, and web logs.
    query = urlencode({"email": normalized})
    request = Request(
        f"{ABSTRACT_EMAIL_REPUTATION_URL}?{query}",
        headers={"Accept": "application/json", "Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            if getattr(response, "status", 200) != 200:
                logger.warning("Abstract Email Reputation API returned HTTP %s", response.status)
                return _remember(cache_key, _result("service_unavailable"))
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        # Never log provider response bodies or exception objects. They may
        # contain the submitted email or implementation details.
        logger.warning("Abstract Email Reputation API returned HTTP %s", error.code)
        return _remember(cache_key, _result("service_unavailable"))
    except (URLError, TimeoutError, OSError, HTTPException):
        logger.warning("Abstract Email Reputation API could not reach the provider")
        return _remember(cache_key, _result("service_unavailable"))
    except Exception:
        logger.warning("Abstract Email Reputation API request failed")
        return _remember(cache_key, _result("service_unavailable"))

    if len(body) > MAX_RESPONSE_BYTES:
        logger.warning("Abstract Email Reputation API response was too large")
        return _remember(cache_key, _result("service_unavailable"))
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        logger.warning("Abstract Email Reputation API returned invalid JSON")
        return _remember(cache_key, _result("service_unavailable"))

    return _remember(cache_key, _classify_response(data, normalized))
