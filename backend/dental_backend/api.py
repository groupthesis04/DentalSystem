import datetime as dt
import hashlib
import hmac
import json
import re
import secrets
from decimal import Decimal, InvalidOperation

from django.core.cache import cache
from django.http import JsonResponse


EMAIL_PATTERN = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,63}$")
PHONE_PATTERN = re.compile(r"^[0-9+() .-]{7,24}$")
TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
TOOTH_PATTERN = re.compile(r"^[0-9#,\.\-\s/]{0,120}$")


def api_error(message, status=400, **extra):
    payload = {"error": message}
    payload.update(extra)
    return JsonResponse(payload, status=status)


def rate_limit(request, bucket, limit, window_seconds):
    """Return a 429 response after repeated sensitive requests from one address."""
    address = request.META.get("REMOTE_ADDR", "unknown")
    digest = hashlib.sha256(f"{bucket}:{address}".encode("utf-8")).hexdigest()
    key = f"drms-rate:{digest}"
    if cache.add(key, 1, timeout=window_seconds):
        return None
    try:
        attempts = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window_seconds)
        attempts = 1
    if attempts > limit:
        return api_error(
            "Too many requests. Please wait and try again.",
            429,
            retry_after=window_seconds,
        )
    return None


def read_json(request):
    if not request.body:
        return {}
    if len(request.body) > 3_000_000:
        raise ValueError("Request is too large.")
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Request body must contain valid JSON.") from error
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")
    if str(payload.get("_website", "")).strip():
        raise ValueError("Request could not be processed.")
    return payload


def make_id(prefix):
    return f"{prefix}_{secrets.token_hex(6)}"


def user_payload(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "role": user.role,
        "profile_image": user.profile_image,
    }


def doctor_required(request):
    return request.user.is_authenticated and request.user.role == "doctor"


def validate_email(value, required=True):
    email = str(value or "").strip().lower()
    if not email and not required:
        return ""
    if not EMAIL_PATTERN.fullmatch(email):
        raise ValueError("Enter a valid email address.")
    return email


def validate_phone(value, required=False):
    phone = str(value or "").strip()
    if not phone and not required:
        return ""
    if not PHONE_PATTERN.fullmatch(phone):
        raise ValueError("Enter a valid contact number.")
    return phone


def validate_name(value, label="name", minimum=2):
    name = " ".join(str(value or "").strip().split())
    if len(name) < minimum or len(name) > 120:
        raise ValueError(f"Enter a valid {label}.")
    if any(character in name for character in "<>\r\n"):
        raise ValueError(f"Enter a valid {label}.")
    return name


def parse_date(value, label="date", required=False):
    text = str(value or "").strip()
    if not text and not required:
        return None
    try:
        return dt.date.fromisoformat(text)
    except ValueError as error:
        raise ValueError(f"Choose a valid {label}.") from error


def parse_time(value):
    text = str(value or "").strip()
    if not TIME_PATTERN.fullmatch(text):
        raise ValueError("Choose a valid appointment time.")
    return dt.time.fromisoformat(text)


def parse_money(value, label):
    try:
        amount = Decimal(str(value or 0)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{label} must be a valid amount.") from error
    if amount < 0 or amount > Decimal("99999999.99"):
        raise ValueError(f"{label} must be between 0 and 99,999,999.99.")
    return amount


def validate_password(password):
    value = str(password or "")
    if len(value) < 8:
        raise ValueError("Password must contain at least 8 characters.")
    if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
        raise ValueError("Password must contain at least one letter and one number.")
    return value


def verify_legacy_password(password, encoded):
    """Accept the old PBKDF2 format once, then the login view upgrades it."""
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256" or len(expected) != 64:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            int(iterations),
        ).hex()
        return hmac.compare_digest(digest, expected)
    except (TypeError, ValueError):
        return False


def split_name(full_name):
    parts = [part for part in str(full_name or "").strip().split() if part]
    if not parts:
        return "", "", ""
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], "", parts[1]
    return parts[0], " ".join(parts[1:-1]), parts[-1]


def calculate_age(birthdate):
    if not birthdate:
        return None
    today = dt.date.today()
    return today.year - birthdate.year - (
        (today.month, today.day) < (birthdate.month, birthdate.day)
    )
