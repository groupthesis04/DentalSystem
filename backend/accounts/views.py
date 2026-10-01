import datetime as dt
import hashlib
import re
import secrets

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.sessions.models import Session
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from communications import sms_provider
from dental_backend.api import (
    api_error,
    calculate_age,
    doctor_required,
    make_id,
    rate_limit,
    read_json,
    split_name,
    user_payload,
    validate_email,
    validate_name,
    validate_password,
    validate_phone,
    verify_legacy_password,
)
from records.models import TreatmentRecord
from scheduling.models import Appointment

from .identity import (
    canonical_mobile,
    creation_conflict,
    identity_candidates,
    normalized_full_name,
)
from .audit import record_audit_event
from .lockout import (
    account_lock_seconds,
    clear_failed_attempts,
    register_failed_attempt,
)
from .models import PatientAccountVerification, PatientProfile, User
from .security_views import _active_user_sessions, record_login_activity


OTP_LIFETIME = dt.timedelta(minutes=5)
OTP_RESEND_COOLDOWN = dt.timedelta(seconds=60)
OTP_HOURLY_LIMIT = 5
OTP_MAX_ATTEMPTS = 5
MATCH_REVIEW_MESSAGE = "A patient record may already exist. Contact the clinic to verify your details."
PRIVACY_NOTICE_VERSION = "registration-2026-10-01"


def patient_payload(profile):
    return {
        "id": profile.id,
        "name": profile.name,
        "first_name": profile.first_name,
        "middle_name": profile.middle_name,
        "last_name": profile.last_name,
        "email": profile.email,
        "phone": profile.phone,
        "phone_number": profile.phone_number,
        "mobile_number": profile.mobile_number,
        "birthdate": profile.birthdate.isoformat() if profile.birthdate else "",
        "age": profile.age if profile.age is not None else "",
        "sex": profile.sex,
        "address": profile.address,
        "nationality": profile.nationality,
        "occupation": profile.occupation,
        "notes": profile.notes,
        "source": "account" if profile.user_id else "profile",
        "profile_image": profile.user.profile_image if profile.user_id else "",
        "role": profile.user.role if profile.user_id else "patient",
        "account_active": profile.user.is_active if profile.user_id else None,
        "privacy_consent_given": profile.privacy_consent_given,
        "privacy_consent_at": profile.privacy_consent_at.isoformat() if profile.privacy_consent_at else None,
        "privacy_version": profile.privacy_version,
        "sms_consent": profile.sms_consent,
        "sms_consent_at": profile.sms_consent_at.isoformat() if profile.sms_consent_at else None,
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat(),
    }


def profile_for_user(user):
    if user.role != "patient":
        return None
    try:
        return user.patient_profile
    except PatientProfile.DoesNotExist:
        first_name, middle_name, last_name = split_name(user.name)
        full_name = normalized_full_name(first_name, middle_name, last_name)
        with transaction.atomic():
            same_id = PatientProfile.objects.select_for_update().filter(id=user.id).first()
            if same_id:
                # A pre-existing clinic record must never be claimed by merely
                # signing in with an account that happens to have the same ID.
                return None
            # Old accounts have no stored birthdate, so a plausible clinic record
            # must be reviewed instead of being claimed or duplicated automatically.
            if creation_conflict(user.email, user.phone, None, full_name):
                return None
            return PatientProfile.objects.create(
                id=user.id,
                user=user,
                first_name=first_name,
                middle_name=middle_name,
                last_name=last_name,
                email=user.email,
                phone_number=user.phone,
                mobile_number=user.phone,
                sms_consent=None,
            )


def authenticated_user_payload(user):
    data = user_payload(user)
    if user.role == "patient":
        profile = profile_for_user(user)
        age = ""
        if profile:
            age = profile.age if profile.age is not None else calculate_age(profile.birthdate)
        data.update(
            {
                "birthdate": profile.birthdate.isoformat() if profile and profile.birthdate else "",
                "age": age,
                "notes": profile.notes if profile else "",
                "profile_verification_required": profile is None,
            }
        )
    return data


@ensure_csrf_cookie
@require_GET
def session(request):
    user = authenticated_user_payload(request.user) if request.user.is_authenticated else None
    return JsonResponse({"user": user, "csrf_token": get_token(request)})


def registration_profile(email, mobile, birthdate, full_name):
    """Identify a clinic record; demographics never authorize linking on their own."""
    matches = []
    possible_conflict = False
    for profile in identity_candidates(email, birthdate, full_name, for_update=True):
        same_email = bool(profile.email and profile.email.casefold() == email)
        same_phone = canonical_mobile(profile.mobile_number or profile.phone_number) == mobile
        same_birthdate = profile.birthdate == birthdate
        same_name = profile.normalized_name == full_name
        if (same_email or not profile.email) and same_phone and same_birthdate and same_name:
            matches.append(profile)
        elif (
            same_email
            or (same_phone and same_birthdate)
            or (same_name and same_birthdate)
            or (same_name and same_phone)
            or (same_phone and not profile.birthdate)
        ):
            possible_conflict = True
    if possible_conflict or len(matches) > 1:
        raise ValueError(MATCH_REVIEW_MESSAGE)
    if matches and matches[0].user_id:
        raise ValueError("This patient record is already linked to an account.")
    return matches[0] if matches else None


def verification_token_hash(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def masked_mobile(phone):
    return "09******" + phone[-3:]


def verification_response(token, phone):
    return JsonResponse({
        "verification_required": True,
        "verification_token": token,
        "masked_mobile": masked_mobile(phone),
        "expires_in": int(OTP_LIFETIME.total_seconds()),
        "resend_after": int(OTP_RESEND_COOLDOWN.total_seconds()),
        "message": "If the information matches an existing patient record, a verification code has been sent to the registered mobile number.",
    }, status=202)


def create_verification(profile, *, email, first_name, middle_name, last_name,
                        birthdate, password_hash, profile_image, remember, phone,
                        privacy_version, sms_consent):
    now = timezone.now()
    recent = PatientAccountVerification.objects.filter(
        patient=profile, created_at__gte=now - dt.timedelta(hours=1)
    ).order_by("-created_at").first()
    if recent and now - recent.created_at < OTP_RESEND_COOLDOWN:
        wait = int((OTP_RESEND_COOLDOWN - (now - recent.created_at)).total_seconds()) + 1
        raise VerificationCooldown(wait)
    if PatientAccountVerification.objects.filter(
        patient=profile, created_at__gte=now - dt.timedelta(hours=1)
    ).count() >= OTP_HOURLY_LIMIT:
        raise VerificationCooldown(3600)
    PatientAccountVerification.objects.filter(patient=profile, is_used=False).update(
        is_used=True, code_hash="", password_hash="", profile_image=""
    )
    token = secrets.token_urlsafe(32)
    code = f"{secrets.randbelow(1_000_000):06d}"
    PatientAccountVerification.objects.create(
        patient=profile,
        token_hash=verification_token_hash(token),
        phone_number=phone,
        code_hash=make_password(code),
        email=email,
        first_name=first_name,
        middle_name=middle_name,
        last_name=last_name,
        birthdate=birthdate,
        password_hash=password_hash,
        profile_image=profile_image,
        remember=remember,
        privacy_version=privacy_version,
        sms_consent=sms_consent,
        expires_at=now + OTP_LIFETIME,
    )
    return token, code


class VerificationCooldown(Exception):
    def __init__(self, seconds):
        self.seconds = seconds


def send_verification_code(phone, token, code):
    body = (
        f"{settings.SMS_CLINIC_NAME}\n"
        f"Your account verification code is {code}. It expires in 5 minutes. "
        "Do not share this code with anyone."
    )
    try:
        _, state = sms_provider.send(phone, body)
    except sms_provider.SmsProviderError as error:
        # An uncertain provider response may still have delivered the code. Keep
        # that challenge valid, but never include the code or number in errors.
        if error.uncertain:
            return verification_response(token, phone)
        PatientAccountVerification.objects.filter(token_hash=verification_token_hash(token)).update(
            is_used=True, code_hash="", password_hash="", profile_image=""
        )
        return api_error("Verification SMS could not be sent. Please try again after a minute.", 503)
    if state in {"failed", "refunded"}:
        PatientAccountVerification.objects.filter(token_hash=verification_token_hash(token)).update(
            is_used=True, code_hash="", password_hash="", profile_image=""
        )
        return api_error("Verification SMS could not be sent. Please try again after a minute.", 503)
    verification = PatientAccountVerification.objects.select_related("patient").filter(
        token_hash=verification_token_hash(token)
    ).first()
    record_audit_event(
        "SMS_SENT",
        target=verification.patient if verification else None,
        metadata={"origin": "system", "channel": "sms"},
    )
    return verification_response(token, phone)


@require_POST
def register(request):
    limited = rate_limit(request, "register", 4, 60 * 60)
    if limited:
        return limited
    # Expired registration credentials are short-lived even when the SMS worker
    # is unavailable; its regular cleanup handles records without new signups.
    PatientAccountVerification.objects.filter(
        created_at__lt=timezone.now() - dt.timedelta(days=1)
    ).delete()
    try:
        payload = read_json(request)
        email = validate_email(payload.get("email"))
    except ValueError as error:
        return api_error(str(error))
    if str(payload.get("role", "patient")).strip().lower() != "patient":
        return api_error("New accounts must be patient accounts.", 403)
    if payload.get("privacy_consent_given") is not True:
        return api_error("Please agree to the patient information notice to create an account.")
    if payload.get("privacy_version") != PRIVACY_NOTICE_VERSION:
        return api_error("The registration notice has changed. Refresh and review it before continuing.", 409)
    if "sms_consent" in payload and not isinstance(payload["sms_consent"], bool):
        return api_error("Choose whether to receive appointment and account-related SMS messages.")
    sms_consent = payload.get("sms_consent", False)
    if User.objects.filter(email__iexact=email).exists():
        return api_error("An account already uses this email.", 409)
    try:
        if payload.get("first_name") or payload.get("last_name"):
            first_name = validate_name(payload.get("first_name"), "first name")
            middle_name = str(payload.get("middle_name", "")).strip()
            if middle_name:
                middle_name = validate_name(middle_name, "middle name")
            last_name = validate_name(payload.get("last_name"), "last name")
        else:
            legacy_name = validate_name(payload.get("name"), "name", 3)
            first_name, middle_name, last_name = split_name(legacy_name)
            first_name = validate_name(first_name, "first name")
            last_name = validate_name(last_name, "last name")
        name = " ".join(part for part in (first_name, middle_name, last_name) if part)
        phone = validate_phone(payload.get("phone"), required=True)
        mobile = canonical_mobile(phone)
        if not mobile:
            raise ValueError("Enter a valid Philippine mobile number.")
        birthdate = parse_birthdate(payload.get("birthdate"))
        password = validate_password(payload.get("password"))
    except ValueError as error:
        return api_error(str(error))
    profile_image = str(payload.get("profile_image", "")).strip()
    if len(profile_image) > 2_500_000:
        return api_error("Profile image is too large.")
    if profile_image and not profile_image.startswith("data:image/"):
        return api_error("Choose a valid profile image.")
    full_name = normalized_full_name(first_name, middle_name, last_name)
    remember = str(payload.get("remember", "")).lower() in {"1", "true", "yes", "on"}
    verification = None
    try:
        with transaction.atomic():
            if User.objects.filter(email__iexact=email).exists():
                return api_error("An account already uses this email.", 409)
            profile = registration_profile(email, mobile, birthdate, full_name)
            if profile:
                if not sms_provider.ready():
                    return api_error("Account verification is temporarily unavailable. Please contact the clinic.", 503)
                try:
                    stored_phone = sms_provider.normalize_phone(profile.mobile_number or profile.phone_number)
                except ValueError:
                    return api_error("The clinic must update the mobile number on this patient record.", 409)
                token, code = create_verification(
                    profile,
                    email=email,
                    first_name=first_name,
                    middle_name=middle_name,
                    last_name=last_name,
                    birthdate=birthdate,
                    password_hash=make_password(password),
                    profile_image=profile_image,
                    remember=remember,
                    phone=stored_phone,
                    privacy_version=PRIVACY_NOTICE_VERSION,
                    sms_consent=sms_consent,
                )
                verification = (stored_phone, token, code)
            else:
                user = User.objects.create_user(
                    id=make_id("usr"),
                    email=email,
                    password=password,
                    name=name,
                    phone=phone,
                    role="patient",
                    profile_image=profile_image,
                )
                profile = PatientProfile.objects.create(
                    id=user.id,
                    user=user,
                    first_name=first_name,
                    middle_name=middle_name,
                    last_name=last_name,
                    email=email,
                    birthdate=birthdate,
                    age=calculate_age(birthdate),
                    phone_number=phone,
                    mobile_number=phone,
                    privacy_consent_given=True,
                    privacy_consent_at=timezone.now(),
                    privacy_version=PRIVACY_NOTICE_VERSION,
                    sms_consent=sms_consent,
                    sms_consent_at=timezone.now(),
                )
                record_audit_event(
                    "PATIENT_CREATED", actor=user, target=profile,
                    metadata={"origin": "patient"},
                )
    except IntegrityError:
        if User.objects.filter(email__iexact=email).exists():
            return api_error("An account already uses this email.", 409)
        return api_error(MATCH_REVIEW_MESSAGE, 409)
    except VerificationCooldown as error:
        return api_error("Please wait before requesting another verification code.", 429, retry_after=error.seconds)
    except ValueError as error:
        return api_error(str(error), 409)

    if verification:
        return send_verification_code(*verification)

    auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.set_expiry(7 * 24 * 60 * 60 if remember else 12 * 60 * 60)
    record_audit_event("LOGIN_SUCCESS", actor=user, request=request)
    return JsonResponse(
        {"user": authenticated_user_payload(user), "csrf_token": get_token(request)},
        status=201,
    )


def requested_verification(payload):
    token = str(payload.get("verification_token", ""))
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise ValueError("Invalid verification request.")
    return token, verification_token_hash(token)


def verification_profile_unchanged(profile, verification):
    try:
        current_phone = sms_provider.normalize_phone(profile.mobile_number or profile.phone_number)
    except ValueError:
        return False
    return (
        current_phone == verification.phone_number
        and profile.birthdate == verification.birthdate
        and profile.normalized_name == normalized_full_name(
            verification.first_name, verification.middle_name, verification.last_name
        )
        and (not profile.email or profile.email.casefold() == verification.email)
    )


@require_POST
def verify_account(request):
    limited = rate_limit(request, "account_verify", 20, 60)
    if limited:
        return limited
    try:
        payload = read_json(request)
        _, token_hash = requested_verification(payload)
    except ValueError as error:
        return api_error(str(error))
    code = str(payload.get("code", "")).strip()
    patient_id = PatientAccountVerification.objects.filter(
        token_hash=token_hash
    ).values_list("patient_id", flat=True).first()
    if not patient_id:
        return api_error("Invalid verification request.")

    try:
        with transaction.atomic():
            profile = PatientProfile.objects.select_for_update().get(pk=patient_id)
            verification = PatientAccountVerification.objects.select_for_update().get(token_hash=token_hash)
            if verification.attempts >= OTP_MAX_ATTEMPTS:
                return api_error("Too many incorrect attempts. Request a new code.", 429)
            if verification.is_used:
                return api_error("This verification code has already been used.", 409)
            if verification.expires_at <= timezone.now():
                return api_error("Verification code expired. Request a new code.", 410)
            if verification.privacy_version != PRIVACY_NOTICE_VERSION:
                return api_error("The registration notice has changed. Please register again.", 409)
            if not re.fullmatch(r"[0-9]{6}", code) or not check_password(code, verification.code_hash):
                verification.attempts += 1
                verification.save(update_fields=["attempts"])
                if verification.attempts >= OTP_MAX_ATTEMPTS:
                    return api_error("Too many incorrect attempts. Request a new code.", 429)
                return api_error("Invalid verification code.")
            if profile.user_id:
                return api_error("This patient record is already linked to an account.", 409)
            if User.objects.filter(email__iexact=verification.email).exists():
                return api_error("An account already uses this email.", 409)
            if not verification_profile_unchanged(profile, verification):
                return api_error(MATCH_REVIEW_MESSAGE, 409)
            user = User.objects.create(
                id=make_id("usr"),
                email=verification.email,
                password=verification.password_hash,
                name=" ".join(filter(None, (
                    verification.first_name, verification.middle_name, verification.last_name
                ))),
                phone=verification.phone_number,
                role="patient",
                profile_image=verification.profile_image,
            )
            profile.user = user
            changed = ["user", "updated_at"]
            profile.privacy_consent_given = True
            profile.privacy_consent_at = timezone.now()
            profile.privacy_version = verification.privacy_version
            profile.sms_consent = verification.sms_consent
            profile.sms_consent_at = timezone.now()
            changed.extend(["privacy_consent_given", "privacy_consent_at", "privacy_version", "sms_consent", "sms_consent_at"])
            if not profile.email:
                profile.email = verification.email
                changed.append("email")
            profile.save(update_fields=changed)
            record_audit_event(
                "PATIENT_UPDATED", actor=user, target=profile,
                metadata={"origin": "patient"},
            )
            if not profile.sms_consent:
                from communications.models import SmsMessage
                SmsMessage.objects.filter(patient=profile, status="queued", is_test=False).update(
                    status="suppressed", error="Patient SMS consent is not active."
                )
            verification.is_used = True
            verification.code_hash = ""
            verification.password_hash = ""
            verification.profile_image = ""
            verification.save(update_fields=["is_used", "code_hash", "password_hash", "profile_image"])
    except IntegrityError:
        return api_error("This patient record is already linked to an account.", 409)

    auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.set_expiry(7 * 24 * 60 * 60 if verification.remember else 12 * 60 * 60)
    record_audit_event("LOGIN_SUCCESS", actor=user, request=request)
    return JsonResponse({"user": authenticated_user_payload(user), "csrf_token": get_token(request)}, status=201)


@require_POST
def resend_account_code(request):
    limited = rate_limit(request, "account_resend", 8, 60 * 60)
    if limited:
        return limited
    try:
        payload = read_json(request)
        _, token_hash = requested_verification(payload)
    except ValueError as error:
        return api_error(str(error))
    patient_id = PatientAccountVerification.objects.filter(
        token_hash=token_hash
    ).values_list("patient_id", flat=True).first()
    if not patient_id:
        return api_error("Invalid verification request.")
    if not sms_provider.ready():
        return api_error("Account verification is temporarily unavailable. Please contact the clinic.", 503)
    try:
        with transaction.atomic():
            profile = PatientProfile.objects.select_for_update().get(pk=patient_id)
            previous = PatientAccountVerification.objects.select_for_update().get(token_hash=token_hash)
            if previous.is_used:
                return api_error("This verification code has already been used.", 409)
            if previous.created_at < timezone.now() - dt.timedelta(days=1):
                return api_error("Verification request expired. Please register again.", 410)
            if previous.privacy_version != PRIVACY_NOTICE_VERSION:
                return api_error("The registration notice has changed. Please register again.", 409)
            if profile.user_id:
                return api_error("This patient record is already linked to an account.", 409)
            if User.objects.filter(email__iexact=previous.email).exists():
                return api_error("An account already uses this email.", 409)
            if not verification_profile_unchanged(profile, previous):
                return api_error(MATCH_REVIEW_MESSAGE, 409)
            stored_phone = previous.phone_number
            token, code = create_verification(
                profile,
                email=previous.email,
                first_name=previous.first_name,
                middle_name=previous.middle_name,
                last_name=previous.last_name,
                birthdate=previous.birthdate,
                password_hash=previous.password_hash,
                profile_image=previous.profile_image,
                remember=previous.remember,
                phone=stored_phone,
                privacy_version=previous.privacy_version,
                sms_consent=previous.sms_consent,
            )
    except VerificationCooldown as error:
        return api_error("Resend available in 60 seconds." if error.seconds <= 60 else "Too many codes requested. Please try again later.", 429, retry_after=error.seconds)
    return send_verification_code(stored_phone, token, code)


@require_POST
def login(request):
    limited = rate_limit(request, "login", 5, 5 * 60)
    if limited:
        return limited
    try:
        payload = read_json(request)
    except ValueError as error:
        return api_error(str(error))
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    user = User.objects.filter(email__iexact=email).first()
    if user:
        retry_after = account_lock_seconds(user)
        if retry_after:
            return api_error("This account is temporarily locked. Try again later.", 429, retry_after=retry_after)
    password_matches = False
    if user:
        try:
            password_matches = user.check_password(password)
        except (TypeError, ValueError):
            password_matches = False
        if user.is_active and not password_matches and verify_legacy_password(password, user.password):
            user.set_password(password)
            user.save(update_fields=["password", "updated_at"])
            password_matches = True
    if not user or not password_matches:
        if user:
            retry_after, newly_locked = register_failed_attempt(user)
            if newly_locked:
                record_audit_event("ACCOUNT_LOCKED", target=user)
            record_audit_event("LOGIN_FAILED", target=user)
            if retry_after:
                return api_error("This account is temporarily locked. Try again later.", 429, retry_after=retry_after)
        else:
            record_audit_event("LOGIN_FAILED")
        return api_error("Email or password is incorrect.", 401)
    if not user.is_active:
        record_audit_event("LOGIN_FAILED", target=user)
        return api_error("This account has been disabled. Please contact Borja Dental Clinic.", 403)

    remember = str(payload.get("remember", "")).lower() in {"1", "true", "yes", "on"}
    clear_failed_attempts(user)
    auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.set_expiry(7 * 24 * 60 * 60 if remember else 12 * 60 * 60)
    record_login_activity(request, user)
    record_audit_event("LOGIN_SUCCESS", actor=user, request=request)
    return JsonResponse({"user": authenticated_user_payload(user), "csrf_token": get_token(request)})


@require_POST
def logout(request):
    if request.user.is_authenticated:
        record_audit_event("LOGOUT", actor=request.user, request=request)
    auth_logout(request)
    return JsonResponse({"ok": True})


@require_http_methods(["PATCH"])
def profile(request):
    if not request.user.is_authenticated:
        return api_error("Authentication is required.", 401)
    try:
        payload = read_json(request)
        name = validate_name(payload.get("name"), "name", 3)
        email = validate_email(payload.get("email"))
        phone = validate_phone(payload.get("phone"))
    except ValueError as error:
        return api_error(str(error))
    duplicate = User.objects.filter(email__iexact=email).exclude(id=request.user.id).exists()
    if duplicate:
        return api_error("An account already uses that email.", 409)
    if PatientProfile.objects.filter(email__iexact=email).exclude(user=request.user).exists():
        return api_error("A patient record already uses that email. Contact the clinic to verify it.", 409)
    profile_image = str(payload.get("profile_image", "")).strip()
    if len(profile_image) > 2_500_000 or (profile_image and not profile_image.startswith("data:image/")):
        return api_error("Choose a valid profile image.")

    user = request.user
    old_name = user.name
    with transaction.atomic():
        patient = profile_for_user(user) if user.role == "patient" else None
        if user.role == "patient" and patient is None:
            return api_error("Your patient record needs clinic verification before it can be changed.", 409)
        user.name = name
        user.email = email
        user.phone = phone
        user.profile_image = profile_image
        user.save()
        if user.role == "patient":
            first_name, middle_name, last_name = split_name(name)
            patient.first_name = first_name
            patient.middle_name = middle_name
            patient.last_name = last_name
            patient.email = email
            patient.phone_number = phone
            patient.mobile_number = phone
            patient.save()
            Appointment.objects.filter(patient=patient).update(
                patient_name=name,
                patient_email=email,
                patient_phone=phone,
            )
            TreatmentRecord.objects.filter(patient=patient).update(patient_name=name)
        else:
            Appointment.objects.filter(doctor=user).update(doctor_name=name)
            TreatmentRecord.objects.filter(doctor=user).update(doctor_name=name)
            if old_name != name:
                Appointment.objects.filter(doctor__isnull=True, doctor_name=old_name).update(doctor_name=name)
    return JsonResponse({"user": authenticated_user_payload(user)})


def update_sms_consent(patient, consent):
    """Persist an explicit patient choice and stop unsent messages on opt-out."""
    patient.sms_consent = consent
    patient.sms_consent_at = timezone.now()
    patient.save(update_fields=["sms_consent", "sms_consent_at", "updated_at"])
    if not consent:
        from communications.models import SmsMessage
        SmsMessage.objects.filter(patient=patient, status="queued", is_test=False).update(
            status="suppressed", error="Patient SMS consent is not active."
        )


@require_http_methods(["GET", "PATCH"])
def sms_preference(request):
    if not request.user.is_authenticated or request.user.role != "patient":
        return api_error("Patient access is required.", 403)
    patient = profile_for_user(request.user)
    if patient is None:
        return api_error("Your patient record needs clinic verification.", 409)
    if request.method == "GET":
        return JsonResponse({
            "sms_consent": patient.sms_consent,
            "sms_consent_at": patient.sms_consent_at.isoformat() if patient.sms_consent_at else None,
            "privacy_consent_given": patient.privacy_consent_given,
            "privacy_consent_at": patient.privacy_consent_at.isoformat() if patient.privacy_consent_at else None,
            "privacy_version": patient.privacy_version,
        })
    try:
        payload = read_json(request)
    except ValueError as error:
        return api_error(str(error))
    if not isinstance(payload.get("sms_consent"), bool):
        return api_error("Choose whether to receive SMS messages.")
    with transaction.atomic():
        patient = PatientProfile.objects.select_for_update().get(pk=patient.pk)
        update_sms_consent(patient, payload["sms_consent"])
        record_audit_event("PATIENT_UPDATED", actor=request.user, target=patient, request=request, metadata={"origin": "patient"})
    return JsonResponse({
        "sms_consent": patient.sms_consent,
        "sms_consent_at": patient.sms_consent_at.isoformat(),
    })


def parse_birthdate(value):
    text = str(value or "").strip()
    if not text:
        raise ValueError("Choose the patient's birthdate.")
    try:
        birthdate = dt.date.fromisoformat(text)
    except ValueError as error:
        raise ValueError("Choose a valid birthdate.") from error
    if birthdate >= dt.date.today() or birthdate < dt.date.today() - dt.timedelta(days=120 * 366):
        raise ValueError("Choose a valid birthdate.")
    return birthdate


def validated_patient(payload):
    first_name = validate_name(payload.get("first_name"), "first name")
    middle_name = str(payload.get("middle_name", "")).strip()
    if middle_name:
        middle_name = validate_name(middle_name, "middle name")
    last_name = validate_name(payload.get("last_name"), "last name")
    email = validate_email(payload.get("email"), required=False)
    phone_number = validate_phone(payload.get("phone_number", payload.get("phone", "")))
    mobile_number = validate_phone(payload.get("mobile_number", payload.get("phone", "")), required=True)
    birthdate = parse_birthdate(payload.get("birthdate"))
    sex = str(payload.get("sex", "")).strip().lower()
    if sex not in {"male", "female", "other", "prefer not to say"}:
        raise ValueError("Choose a valid sex value.")
    address = str(payload.get("address", "")).strip()
    nationality = str(payload.get("nationality", "")).strip()
    occupation = str(payload.get("occupation", "")).strip()
    if len(address) < 5:
        raise ValueError("Enter the patient's home address.")
    if len(nationality) < 2:
        raise ValueError("Enter the patient's nationality.")
    if len(occupation) < 2:
        raise ValueError("Enter the patient's occupation.")
    return {
        "first_name": first_name,
        "middle_name": middle_name,
        "last_name": last_name,
        "email": email,
        "phone_number": phone_number,
        "mobile_number": mobile_number,
        "birthdate": birthdate,
        "age": calculate_age(birthdate),
        "sex": sex,
        "address": address[:300],
        "nationality": nationality[:80],
        "occupation": occupation[:120],
        "notes": str(payload.get("notes", "")).strip()[:1000],
    }


@require_http_methods(["GET", "POST", "PATCH", "DELETE"])
def patients(request):
    if not doctor_required(request):
        return api_error("Doctor access is required.", 403)

    if request.method == "GET":
        data = []
        for patient in PatientProfile.objects.select_related("user").order_by("first_name", "last_name"):
            item = patient_payload(patient)
            record_totals = TreatmentRecord.objects.filter(patient=patient).aggregate(
                charged=Sum("amount_charged"),
                paid=Sum("amount_paid"),
                balance=Sum("balance"),
            )
            last_record = TreatmentRecord.objects.filter(patient=patient).order_by("-treatment_date").first()
            item.update(
                {
                    "appointment_count": Appointment.objects.filter(patient=patient).count(),
                    "record_count": TreatmentRecord.objects.filter(patient=patient).count(),
                    "last_visit": last_record.treatment_date.isoformat() if last_record else "",
                    "total_amount_charged": float(record_totals["charged"] or 0),
                    "total_amount_paid": float(record_totals["paid"] or 0),
                    "total_balance": float(record_totals["balance"] or 0),
                }
            )
            data.append(item)
        return JsonResponse({"patients": data})

    try:
        payload = read_json(request)
    except ValueError as error:
        return api_error(str(error))

    if request.method == "PATCH" and payload.get("action") == "account_status":
        if not isinstance(payload.get("is_active"), bool):
            return api_error("Choose an active or disabled account status.")
        with transaction.atomic():
            patient = PatientProfile.objects.select_for_update().select_related("user").filter(
                pk=str(payload.get("id", "")).strip(), user__role="patient"
            ).first()
            if not patient:
                return api_error("Patient account not found.", 404)
            account = patient.user
            if account.is_active != payload["is_active"]:
                account.is_active = payload["is_active"]
                account.save(update_fields=["is_active", "updated_at"])
                if not account.is_active:
                    Session.objects.filter(session_key__in=list(_active_user_sessions(account.pk))).delete()
                record_audit_event(
                    "ACCOUNT_ENABLED" if account.is_active else "ACCOUNT_DISABLED",
                    actor=request.user, target=account, request=request,
                )
        return JsonResponse({"patient": patient_payload(patient)})

    if request.method == "PATCH" and payload.get("action") == "sms_consent":
        if not isinstance(payload.get("sms_consent"), bool):
            return api_error("Record the patient's SMS choice before saving.")
        with transaction.atomic():
            patient = PatientProfile.objects.select_for_update().select_related("user").filter(
                pk=str(payload.get("id", "")).strip()
            ).first()
            if not patient:
                return api_error("Patient not found.", 404)
            update_sms_consent(patient, payload["sms_consent"])
            record_audit_event("PATIENT_UPDATED", actor=request.user, target=patient, request=request, metadata={"origin": "doctor"})
        return JsonResponse({"patient": patient_payload(patient)})

    if request.method == "DELETE":
        with transaction.atomic():
            patient = PatientProfile.objects.select_for_update().filter(
                id=str(payload.get("id", "")).strip()
            ).first()
            if not patient:
                return api_error("Patient not found.", 404)
            if patient.user_id:
                return api_error("Patient login accounts cannot be deleted from this section.", 403)
            if Appointment.objects.filter(patient=patient).exists():
                return api_error("This patient has appointment history and cannot be deleted.", 409)
            for treatment in TreatmentRecord.objects.filter(patient=patient):
                record_audit_event(
                    "TREATMENT_DELETED", actor=request.user, target=treatment, request=request
                )
            record_audit_event("PATIENT_DELETED", actor=request.user, target=patient, request=request)
            TreatmentRecord.objects.filter(patient=patient).delete()
            patient.delete()
        return JsonResponse({"ok": True})

    try:
        values = validated_patient(payload)
    except ValueError as error:
        return api_error(str(error))
    patient_id = str(payload.get("id", "")).strip()
    if User.objects.filter(email__iexact=values["email"]).exists():
        return api_error("A patient account already uses that email.", 409)
    normalized_name = normalized_full_name(
        values["first_name"], values["middle_name"], values["last_name"]
    )
    if creation_conflict(
        values["email"], values["mobile_number"], values["birthdate"], normalized_name,
        exclude_id=patient_id or None,
    ):
        return api_error("A patient record may already exist. Select or edit that patient instead.", 409)

    if request.method == "POST":
        patient = PatientProfile(id=make_id("pat"), **values)
        status = 201
    else:
        patient = PatientProfile.objects.filter(id=patient_id, user__isnull=True).first()
        if not patient:
            return api_error("Only clinic patient records can be edited here.", 403)
        for field, value in values.items():
            setattr(patient, field, value)
        status = 200
    try:
        with transaction.atomic():
            patient.save()
            TreatmentRecord.objects.filter(patient=patient).update(patient_name=patient.name)
            record_audit_event(
                "PATIENT_CREATED" if request.method == "POST" else "PATIENT_UPDATED",
                actor=request.user, target=patient, request=request, metadata={"origin": "doctor"},
            )
    except IntegrityError:
        return api_error("A patient record with these details already exists.", 409)
    return JsonResponse({"patient": patient_payload(patient)}, status=status)
