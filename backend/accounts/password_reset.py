"""Email OTP password recovery, independent of patient registration SMS."""

import datetime as dt
import hashlib
import hmac
import html
import json
import logging
import re
import secrets
from email.utils import formataddr
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password as django_validate_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from dental_backend.api import api_error, rate_limit, read_json, validate_email, validate_password

from .audit import record_audit_event
from .lockout import clear_failed_attempts
from .models import PasswordResetVerification, User
from .security_views import _active_user_sessions


logger = logging.getLogger(__name__)

OTP_LIFETIME = dt.timedelta(minutes=5)
OTP_RESEND_COOLDOWN = dt.timedelta(seconds=60)
OTP_HOURLY_LIMIT = 5
OTP_MAX_ATTEMPTS = 5
GENERIC_REQUEST_MESSAGE = "If an account exists for this email, a verification code will be sent."
EMAIL_UNAVAILABLE_MESSAGE = "Password recovery is temporarily unavailable. Please try again later."
INVALID_CHALLENGE_MESSAGE = "Invalid or expired verification session. Please request a new code."


class PasswordResetEmailError(Exception):
    """A safe marker for a Resend request that was not confirmed as accepted."""


def _safe_resend_error_details(error, *, code, to_email):
    """Keep useful Resend error fields without logging the request or secrets."""
    try:
        raw = error.read(4097)
    except Exception:
        return "unreadable_response", "Unable to read provider response"
    if len(raw) > 4096:
        return "oversized_response", "Provider response exceeded logging limit"
    if raw.strip() == b"error code: 1010":
        return "cloudflare_1010", "Email API edge blocked the HTTP client signature"
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "non_json_response", "Provider response was not JSON"
    if not isinstance(payload, dict):
        return "invalid_response", "Provider response was not a JSON object"

    name = payload.get("name")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name):
        name = "unknown_error"

    message = payload.get("message")
    if not isinstance(message, str):
        return name, "Provider did not include an error message"
    message = " ".join(message.split())
    for secret in (settings.RESEND_API_KEY, code, to_email, settings.RESEND_FROM_EMAIL):
        if secret:
            message = message.replace(secret, "[redacted]")
    message = re.sub(r"(?i)Bearer\s+\S+", "Bearer [redacted]", message)
    message = re.sub(r"\bre_[A-Za-z0-9_-]+\b", "[redacted]", message)
    message = re.sub(r"(?<![0-9])[0-9]{6}(?![0-9])", "[redacted]", message)
    message = re.sub(r"[A-Za-z0-9_-]{43,}", "[redacted]", message)
    message = re.sub(r"[^\s@<>]+@[^\s@<>]+", "[email redacted]", message)
    return name, message[:500] or "Provider did not include an error message"


def email_delivery_ready():
    return bool(settings.RESEND_API_KEY and settings.RESEND_FROM_EMAIL)


def send_password_reset_email(to_email, code):
    """Ask Resend to accept one email addressed only to a stored User.email."""
    if not email_delivery_ready():
        raise PasswordResetEmailError("Resend sender is not configured")

    sender_name = settings.RESEND_FROM_NAME or "BORJA Dental Clinic"
    if any(character in sender_name for character in "\r\n"):
        raise PasswordResetEmailError("Invalid sender name")
    try:
        sender = formataddr((sender_name, validate_email(settings.RESEND_FROM_EMAIL)))
    except ValueError as error:
        raise PasswordResetEmailError("Invalid sender email") from error

    plain_text = (
        "BORJA Dental Clinic\n\n"
        "Password Reset Request\n\n"
        "We received a request to reset the password for your BORJA Dental Clinic account.\n\n"
        f"Your verification code is: {code}\n\n"
        "This code will expire in 5 minutes.\n\n"
        "If you did not request a password reset, you can safely ignore this email.\n\n"
        "For your security, never share this verification code with anyone.\n\n"
        "BORJA Dental Clinic"
    )
    safe_code = html.escape(code)
    html_body = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Password Reset Verification Code</title></head>'
        '<body lang="en" dir="ltr" style="margin:0;background:#f8f5ef;color:#1b1813;font-family:Arial,sans-serif">'
        '<main style="max-width:520px;margin:24px auto;padding:32px;background:#fff;'
        'border:1px solid #e8d8b7;border-radius:12px">'
        '<p style="margin:0 0 24px;color:#886321;font-size:14px;font-weight:700">BORJA Dental Clinic</p>'
        '<h1 style="margin:0 0 16px;font-size:24px">Password Reset Request</h1>'
        '<p style="font-size:16px;line-height:1.5">We received a request to reset the password '
        'for your BORJA Dental Clinic account.</p>'
        '<p style="font-size:16px">Your verification code is:</p>'
        f'<p style="margin:20px 0;text-align:center;font-family:monospace;font-size:32px;'
        f'font-weight:700;letter-spacing:8px;color:#1b1813">{safe_code}</p>'
        '<p style="font-size:16px;line-height:1.5">This code will expire in 5 minutes.</p>'
        '<p style="font-size:16px;line-height:1.5">If you did not request a password reset, '
        'you can safely ignore this email.</p>'
        '<p style="font-size:16px;line-height:1.5">For your security, never share this '
        'verification code with anyone.</p>'
        '<p style="margin:24px 0 0;color:#886321;font-weight:700">BORJA Dental Clinic</p>'
        '</main></body></html>'
    )
    body = json.dumps({
        "from": sender,
        "to": [to_email],
        "subject": "BORJA Dental Clinic – Password Reset Verification Code",
        "html": html_body,
        "text": plain_text,
    }).encode("utf-8")
    request = Request(
        "https://api.resend.com/emails",
        data=body,
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "BORJA-Dental-Clinic/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            if not 200 <= response.status < 300:
                raise PasswordResetEmailError("Resend did not accept the email")
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        provider_name, provider_message = _safe_resend_error_details(
            error, code=code, to_email=to_email
        )
        sender_domain = settings.RESEND_FROM_EMAIL.rsplit("@", 1)[-1].lower()
        key_has_boundary_quotes = (
            settings.RESEND_API_KEY.startswith(("'", '"'))
            or settings.RESEND_API_KEY.endswith(("'", '"'))
        )
        logger.warning(
            "Resend password reset email request rejected. HTTP %s. Error: %s. "
            "Reason: %s. Sender domain: %s. API key has boundary quotes: %s",
            error.code, provider_name, provider_message, sender_domain, key_has_boundary_quotes,
        )
        raise PasswordResetEmailError("Resend rejected the email") from error
    except (URLError, TimeoutError, OSError) as error:
        logger.warning("Resend password reset email request failed at transport level.")
        raise PasswordResetEmailError("Resend request could not be confirmed") from error
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        logger.warning("Resend password reset email response was invalid.")
        raise PasswordResetEmailError("Resend response could not be confirmed") from error

    if not isinstance(data, dict) or not data.get("id"):
        logger.warning("Resend password reset email response did not include an ID.")
        raise PasswordResetEmailError("Resend response could not be confirmed")


def _email_key(email):
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), email.casefold().encode("utf-8"), hashlib.sha256).hexdigest()


def _token_hash(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _requested_token(payload):
    token = str(payload.get("reset_token", ""))
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise ValueError(INVALID_CHALLENGE_MESSAGE)
    return _token_hash(token)


def _masked_email(email):
    local, domain = email.split("@", 1)
    return f"{local[:2]}***@{domain}"


def _challenge_response(token, masked_email):
    return JsonResponse({
        "verification_required": True,
        "reset_token": token,
        "masked_email": masked_email,
        "expires_in": int(OTP_LIFETIME.total_seconds()),
        "resend_after": int(OTP_RESEND_COOLDOWN.total_seconds()),
        "message": GENERIC_REQUEST_MESSAGE,
    }, status=202)


def _request_limit(email_key, now):
    recent = PasswordResetVerification.objects.filter(email_key=email_key, created_at__gte=now - dt.timedelta(hours=1))
    if recent.count() >= OTP_HOURLY_LIMIT:
        return api_error("Too many codes requested. Please try again later.", 429, retry_after=3600)
    latest = recent.filter(is_used=False).order_by("-created_at", "-id").first()
    if latest and now - latest.created_at < OTP_RESEND_COOLDOWN:
        retry_after = int((OTP_RESEND_COOLDOWN - (now - latest.created_at)).total_seconds()) + 1
        return api_error("Please wait before requesting another verification code.", 429, retry_after=retry_after)
    return None


def _create_challenge(user, email_key, masked_email, now):
    token = secrets.token_urlsafe(32)
    code = f"{secrets.randbelow(1_000_000):06d}"
    previous = PasswordResetVerification.objects.filter(email_key=email_key, is_used=False).order_by("-created_at", "-id").first()
    if previous and previous.code_hash and check_password(code, previous.code_hash):
        # A fresh code must differ from the code it replaces, even in the
        # unlikely event that the random draw repeats the previous six digits.
        code = f"{(int(code) + 1) % 1_000_000:06d}"
    PasswordResetVerification.objects.filter(email_key=email_key, is_used=False).update(
        is_used=True, code_hash=""
    )
    challenge = PasswordResetVerification.objects.create(
        user=user,
        email_key=email_key,
        masked_email=masked_email,
        token_hash=_token_hash(token),
        # A decoy gets a real password hash for comparable verification cost,
        # but its unknown random value cannot be a six-digit OTP.
        code_hash=make_password(code if user else secrets.token_urlsafe(32)),
        expires_at=now + OTP_LIFETIME,
        created_at=now,
    )
    return challenge, token, code


def _discard_undelivered_code(challenge):
    """Keep the generic challenge flow while making an unsent code unusable."""
    PasswordResetVerification.objects.filter(pk=challenge.pk).update(
        code_hash=make_password(secrets.token_urlsafe(32))
    )


@require_POST
def request_password_reset(request):
    limited = rate_limit(request, "password_reset_request", 10, 15 * 60)
    if limited:
        return limited
    try:
        email = validate_email(read_json(request).get("email"))
    except ValueError as error:
        return api_error(str(error))
    if not email_delivery_ready():
        return api_error(EMAIL_UNAVAILABLE_MESSAGE, 503)

    now = timezone.now()
    email_key = _email_key(email)
    # Retain one day of requests for hourly enforcement, then remove expired
    # hashes and decoys on subsequent recovery requests.
    PasswordResetVerification.objects.filter(created_at__lt=now - dt.timedelta(days=1)).delete()
    with transaction.atomic():
        user = User.objects.select_for_update().filter(email__iexact=email).first()
        if user and not user.is_active:
            user = None
        limit_error = _request_limit(email_key, now)
        if limit_error:
            return limit_error
        challenge, token, code = _create_challenge(user, email_key, _masked_email(email), now)

    if user:
        try:
            send_password_reset_email(user.email, code)
        except PasswordResetEmailError:
            _discard_undelivered_code(challenge)
    return _challenge_response(token, challenge.masked_email)


@require_POST
def verify_password_reset(request):
    limited = rate_limit(request, "password_reset_verify", 20, 60)
    if limited:
        return limited
    try:
        payload = read_json(request)
        token_hash = _requested_token(payload)
    except ValueError as error:
        return api_error(str(error))
    code = str(payload.get("code", ""))

    original = PasswordResetVerification.objects.only("id", "user_id").filter(token_hash=token_hash).first()
    if not original:
        return api_error(INVALID_CHALLENGE_MESSAGE)
    with transaction.atomic():
        user = User.objects.select_for_update().filter(pk=original.user_id).first() if original.user_id else None
        challenge = PasswordResetVerification.objects.select_for_update().filter(pk=original.pk, token_hash=token_hash).first()
        if not challenge:
            return api_error(INVALID_CHALLENGE_MESSAGE)
        if challenge.is_used or challenge.is_verified:
            return api_error("This verification code has already been used.", 409)
        if challenge.expires_at <= timezone.now():
            return api_error("Verification code expired. Request a new code.", 410)
        if challenge.attempts >= OTP_MAX_ATTEMPTS:
            return api_error("Too many incorrect attempts. Request a new code.", 429)

        correct_code = bool(re.fullmatch(r"[0-9]{6}", code)) and check_password(code, challenge.code_hash)
        eligible_user = bool(
            user and user.is_active and challenge.user_id == user.pk
            and _email_key(user.email) == challenge.email_key
        )
        if not correct_code or not eligible_user:
            challenge.attempts += 1
            challenge.save(update_fields=["attempts"])
            if challenge.attempts >= OTP_MAX_ATTEMPTS:
                return api_error("Too many incorrect attempts. Request a new code.", 429)
            return api_error("Invalid or expired verification code.")

        challenge.is_verified = True
        challenge.verified_at = timezone.now()
        challenge.code_hash = ""
        challenge.save(update_fields=["is_verified", "verified_at", "code_hash"])
    return JsonResponse({"verified": True})


@require_POST
def resend_password_reset(request):
    limited = rate_limit(request, "password_reset_resend", 8, 60 * 60)
    if limited:
        return limited
    if not email_delivery_ready():
        return api_error(EMAIL_UNAVAILABLE_MESSAGE, 503)
    try:
        token_hash = _requested_token(read_json(request))
    except ValueError as error:
        return api_error(str(error))

    # Lock the User before the challenge to match request/confirm lock order.
    original = PasswordResetVerification.objects.only("id", "user_id").filter(token_hash=token_hash).first()
    if not original:
        return api_error(INVALID_CHALLENGE_MESSAGE)
    now = timezone.now()
    with transaction.atomic():
        user = User.objects.select_for_update().filter(pk=original.user_id).first() if original.user_id else None
        previous = PasswordResetVerification.objects.select_for_update().filter(pk=original.pk, token_hash=token_hash).first()
        if not previous or previous.is_used or previous.is_verified:
            return api_error(INVALID_CHALLENGE_MESSAGE, 409)
        if previous.expires_at <= now:
            return api_error(INVALID_CHALLENGE_MESSAGE, 410)
        if user and (not user.is_active or _email_key(user.email) != previous.email_key):
            user = None
        limit_error = _request_limit(previous.email_key, now)
        if limit_error:
            return limit_error
        challenge, token, code = _create_challenge(user, previous.email_key, previous.masked_email, now)

    if user:
        try:
            send_password_reset_email(user.email, code)
        except PasswordResetEmailError:
            _discard_undelivered_code(challenge)
    return _challenge_response(token, challenge.masked_email)


def _new_password(user, payload):
    new_password = validate_password(payload.get("new_password"))
    if new_password != str(payload.get("confirm_password", "")):
        raise ValueError("New passwords do not match.")
    if user.check_password(new_password):
        raise ValueError("Choose a new password that differs from your current password.")
    if not any(character.isupper() for character in new_password) or not any(
        character.islower() for character in new_password
    ):
        raise ValueError("New password must include uppercase and lowercase letters.")
    if not any(not character.isalnum() and not character.isspace() for character in new_password):
        raise ValueError("New password must include a special character.")
    django_validate_password(new_password, user=user)
    return new_password


@require_POST
def confirm_password_reset(request):
    limited = rate_limit(request, "password_reset_confirm", 8, 15 * 60)
    if limited:
        return limited
    try:
        payload = read_json(request)
        token_hash = _requested_token(payload)
    except ValueError as error:
        return api_error(str(error))

    original = PasswordResetVerification.objects.only("id", "user_id").filter(token_hash=token_hash).first()
    if not original:
        return api_error(INVALID_CHALLENGE_MESSAGE)
    with transaction.atomic():
        user = User.objects.select_for_update().filter(pk=original.user_id).first()
        challenge = PasswordResetVerification.objects.select_for_update().filter(pk=original.pk, token_hash=token_hash).first()
        if not user or not challenge or not user.is_active or _email_key(user.email) != challenge.email_key:
            return api_error(INVALID_CHALLENGE_MESSAGE)
        if (
            challenge.is_used or challenge.expires_at <= timezone.now()
            or not challenge.is_verified or challenge.attempts >= OTP_MAX_ATTEMPTS
        ):
            return api_error(INVALID_CHALLENGE_MESSAGE)

        try:
            new_password = _new_password(user, payload)
        except ValueError as error:
            return api_error(str(error))
        except ValidationError as error:
            return api_error(" ".join(error.messages))

        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        now = timezone.now()
        challenge.is_used = True
        challenge.used_at = now
        challenge.code_hash = ""
        challenge.save(update_fields=["is_used", "used_at", "code_hash"])
        PasswordResetVerification.objects.filter(user=user, is_used=False).exclude(pk=challenge.pk).update(
            is_used=True, code_hash=""
        )
        clear_failed_attempts(user)
        session_keys = list(_active_user_sessions(user.pk))
        if session_keys:
            Session.objects.filter(session_key__in=session_keys).delete()
        record_audit_event("PASSWORD_RESET", target=user, metadata={"channel": "email"})
    return JsonResponse({"ok": True})
