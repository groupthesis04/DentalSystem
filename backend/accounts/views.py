import datetime as dt

from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

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

from .models import PatientProfile, User


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
        return PatientProfile.objects.create(
            id=user.id,
            user=user,
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
            email=user.email,
            phone_number=user.phone,
            mobile_number=user.phone,
        )


def authenticated_user_payload(user):
    data = user_payload(user)
    if user.role == "patient":
        profile = profile_for_user(user)
        data.update(
            {
                "birthdate": profile.birthdate.isoformat() if profile.birthdate else "",
                "age": profile.age if profile.age is not None else calculate_age(profile.birthdate),
                "notes": profile.notes,
            }
        )
    return data


@ensure_csrf_cookie
@require_GET
def session(request):
    user = authenticated_user_payload(request.user) if request.user.is_authenticated else None
    return JsonResponse({"user": user, "csrf_token": get_token(request)})


@require_POST
def register(request):
    limited = rate_limit(request, "register", 4, 60 * 60)
    if limited:
        return limited
    try:
        payload = read_json(request)
        name = validate_name(payload.get("name"), "name", 3)
        email = validate_email(payload.get("email"))
        phone = validate_phone(payload.get("phone"))
        password = validate_password(payload.get("password"))
    except ValueError as error:
        return api_error(str(error))
    if str(payload.get("role", "patient")).strip().lower() != "patient":
        return api_error("New accounts must be patient accounts.", 403)
    profile_image = str(payload.get("profile_image", "")).strip()
    if len(profile_image) > 2_500_000:
        return api_error("Profile image is too large.")
    if profile_image and not profile_image.startswith("data:image/"):
        return api_error("Choose a valid profile image.")
    if User.objects.filter(email__iexact=email).exists() or PatientProfile.objects.filter(email__iexact=email).exists():
        return api_error("A patient record or account already uses that email.", 409)

    first_name, middle_name, last_name = split_name(name)
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                id=make_id("usr"),
                email=email,
                password=password,
                name=name,
                phone=phone,
                role="patient",
                profile_image=profile_image,
            )
            PatientProfile.objects.create(
                id=user.id,
                user=user,
                first_name=first_name,
                middle_name=middle_name,
                last_name=last_name,
                email=email,
                phone_number=phone,
                mobile_number=phone,
            )
    except IntegrityError:
        return api_error("A patient record or account already uses that email.", 409)

    auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.set_expiry(7 * 24 * 60 * 60 if str(payload.get("remember", "")).lower() in {"1", "true", "yes", "on"} else 12 * 60 * 60)
    return JsonResponse(
        {"user": authenticated_user_payload(user), "csrf_token": get_token(request)},
        status=201,
    )


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
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    password_matches = False
    if user:
        try:
            password_matches = user.check_password(password)
        except (TypeError, ValueError):
            password_matches = False
        if not password_matches and verify_legacy_password(password, user.password):
            user.set_password(password)
            user.save(update_fields=["password", "updated_at"])
            password_matches = True
    if not user or not password_matches:
        return api_error("Email or password is incorrect.", 401)

    auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.set_expiry(7 * 24 * 60 * 60 if str(payload.get("remember", "")).lower() in {"1", "true", "yes", "on"} else 12 * 60 * 60)
    return JsonResponse({"user": authenticated_user_payload(user), "csrf_token": get_token(request)})


@require_POST
def logout(request):
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
    profile_image = str(payload.get("profile_image", "")).strip()
    if len(profile_image) > 2_500_000 or (profile_image and not profile_image.startswith("data:image/")):
        return api_error("Choose a valid profile image.")

    user = request.user
    old_name = user.name
    with transaction.atomic():
        user.name = name
        user.email = email
        user.phone = phone
        user.profile_image = profile_image
        user.save()
        if user.role == "patient":
            patient = profile_for_user(user)
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
    email = validate_email(payload.get("email"))
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

    if request.method == "DELETE":
        patient = PatientProfile.objects.filter(id=str(payload.get("id", "")).strip()).first()
        if not patient:
            return api_error("Patient not found.", 404)
        if patient.user_id:
            return api_error("Patient login accounts cannot be deleted from this section.", 403)
        if Appointment.objects.filter(patient=patient).exists():
            return api_error("This patient has appointment history and cannot be deleted.", 409)
        with transaction.atomic():
            TreatmentRecord.objects.filter(patient=patient).delete()
            patient.delete()
        return JsonResponse({"ok": True})

    try:
        values = validated_patient(payload)
    except ValueError as error:
        return api_error(str(error))
    patient_id = str(payload.get("id", "")).strip()
    duplicate_email = PatientProfile.objects.filter(email__iexact=values["email"])
    if patient_id:
        duplicate_email = duplicate_email.exclude(id=patient_id)
    if duplicate_email.exists() or User.objects.filter(email__iexact=values["email"]).exists():
        return api_error("A patient record or account already uses that email.", 409)
    normalized_name = " ".join(
        part for part in (values["first_name"], values["middle_name"], values["last_name"]) if part
    ).casefold()
    identity = PatientProfile.objects.filter(normalized_name=normalized_name, birthdate=values["birthdate"])
    if patient_id:
        identity = identity.exclude(id=patient_id)
    if identity.exists():
        return api_error("A patient with the same full name and birthdate already exists.", 409)

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
    patient.save()
    TreatmentRecord.objects.filter(patient=patient).update(patient_name=patient.name)
    return JsonResponse({"patient": patient_payload(patient)}, status=status)
