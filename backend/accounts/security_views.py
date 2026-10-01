"""Authenticated doctor account security and session controls."""

import datetime as dt
import hashlib

from django.contrib.auth import SESSION_KEY, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password as django_validate_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from dental_backend.api import (
    api_error, doctor_required, rate_limit, read_json, validate_email,
    validate_password, validate_phone,
)

from .identity import canonical_mobile
from .audit import record_audit_event
from .models import AccountAuthState, AccountLoginActivity, User


def _session_hash(session_key):
    return hashlib.sha256(session_key.encode("ascii")).hexdigest() if session_key else ""


def _device_label(user_agent):
    """Describe only what the browser reports; do not infer a physical device or location."""
    agent = user_agent or ""
    browser = next(
        (label for marker, label in (
            ("Edg/", "Edge"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"),
            ("Safari/", "Safari"),
        ) if marker in agent),
        "Unknown browser",
    )
    platform = next(
        (label for marker, label in (
            ("Windows", "Windows"), ("Android", "Android"), ("iPhone", "iPhone"),
            ("iPad", "iPad"), ("Macintosh", "macOS"), ("Linux", "Linux"),
        ) if marker in agent),
        "Unknown platform",
    )
    return f"{platform} · {browser}"


def record_login_activity(request, user):
    """Record a successful login without storing the usable session key."""
    if not request.session.session_key:
        request.session.save()
    AccountLoginActivity.objects.create(
        user=user,
        user_agent=str(request.META.get("HTTP_USER_AGENT", ""))[:255],
        session_key_hash=_session_hash(request.session.session_key),
    )


def _active_user_sessions(user_id):
    for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator(chunk_size=500):
        if str(session.get_decoded().get(SESSION_KEY, "")) == str(user_id):
            yield session.session_key


@require_GET
def security(request):
    if not doctor_required(request):
        return api_error("Doctor access is required.", 403)

    current_session = request.session.session_key
    current_hash = _session_hash(current_session)
    activity = AccountLoginActivity.objects.filter(user=request.user).order_by("-created_at", "-id")[:10]
    auth_state = AccountAuthState.objects.filter(user=request.user).first()
    return JsonResponse({
        "is_active": request.user.is_active,
        "last_login": request.user.last_login.isoformat() if request.user.last_login else None,
        "recovery_email": request.user.recovery_email or request.user.email,
        "recovery_mobile_number": request.user.recovery_mobile_number or request.user.phone,
        "login_activity": [
            {
                "id": entry.id,
                "device": _device_label(entry.user_agent),
                "created_at": entry.created_at.isoformat(),
                "is_current": bool(current_hash and entry.session_key_hash == current_hash),
            }
            for entry in activity
        ],
        "other_sessions_count": sum(key != current_session for key in _active_user_sessions(request.user.pk)),
        "login_failed_attempts": (
            auth_state.failed_attempts
            if auth_state and auth_state.last_failed_at and auth_state.last_failed_at >= timezone.now() - dt.timedelta(minutes=15)
            else 0
        ),
        "login_locked_until": auth_state.locked_until.isoformat() if auth_state and auth_state.locked_until and auth_state.locked_until > timezone.now() else None,
    })


@require_POST
def change_password(request):
    if not doctor_required(request):
        return api_error("Doctor access is required.", 403)
    limited = rate_limit(request, f"account-password:{request.user.pk}", 5, 15 * 60)
    if limited:
        return limited
    try:
        payload = read_json(request)
        current_password = str(payload.get("current_password", ""))
        new_password = validate_password(payload.get("new_password"))
        if new_password != str(payload.get("confirm_password", "")):
            raise ValueError("New passwords do not match.")
        if not request.user.check_password(current_password):
            return api_error("Current password is incorrect.", 400)
        if new_password == current_password:
            raise ValueError("Choose a new password that differs from your current password.")
        if not any(character.isupper() for character in new_password) or not any(
            character.islower() for character in new_password
        ):
            raise ValueError("New password must include uppercase and lowercase letters.")
        if not any(not character.isalnum() and not character.isspace() for character in new_password):
            raise ValueError("New password must include a special character.")
        django_validate_password(new_password, user=request.user)
    except ValueError as error:
        return api_error(str(error))
    except ValidationError as error:
        return api_error(" ".join(error.messages))

    old_session_hash = _session_hash(request.session.session_key)
    user = request.user
    with transaction.atomic():
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
    update_session_auth_hash(request, user)
    AccountLoginActivity.objects.filter(
        user=user, session_key_hash=old_session_hash
    ).update(
        session_key_hash=_session_hash(request.session.session_key)
    )
    record_audit_event("PASSWORD_CHANGED", actor=user, target=user, request=request)
    return JsonResponse({"ok": True, "csrf_token": get_token(request)})


@require_http_methods(["PATCH"])
def recovery_contact(request):
    if not doctor_required(request):
        return api_error("Doctor access is required.", 403)
    limited = rate_limit(request, f"account-recovery:{request.user.pk}", 10, 15 * 60)
    if limited:
        return limited
    try:
        payload = read_json(request)
        email = validate_email(payload.get("email"), required=False)
        mobile = validate_phone(payload.get("mobile_number"), required=False)
        if mobile and not canonical_mobile(mobile):
            raise ValueError("Enter a valid Philippine mobile number.")
        if not email and not mobile:
            raise ValueError("Enter a recovery email or mobile number.")
    except ValueError as error:
        return api_error(str(error))
    if not request.user.check_password(str(payload.get("current_password", ""))):
        return api_error("Current password is incorrect.", 400)
    if email and User.objects.filter(
        Q(email__iexact=email) | Q(recovery_email__iexact=email)
    ).exclude(pk=request.user.pk).exists():
        return api_error("An account already uses that email.", 409)

    user = request.user
    user.recovery_email = email
    user.recovery_mobile_number = mobile
    user.save(update_fields=["recovery_email", "recovery_mobile_number", "updated_at"])
    return JsonResponse({
        "recovery_email": user.recovery_email or user.email,
        "recovery_mobile_number": user.recovery_mobile_number or user.phone,
    })


@require_POST
def logout_other_devices(request):
    if not doctor_required(request):
        return api_error("Doctor access is required.", 403)
    current_session = request.session.session_key
    other_keys = [
        key for key in _active_user_sessions(request.user.pk) if key != current_session
    ]
    if other_keys:
        Session.objects.filter(session_key__in=other_keys).delete()
    return JsonResponse({"ok": True, "revoked_count": len(other_keys)})
