import datetime as dt

from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from accounts.models import PatientProfile, User
from clinic.models import Service
from communications.services import create_notification, notify_doctors
from communications.sms import appointment_event
from dental_backend.api import (
    api_error,
    calculate_age,
    doctor_required,
    make_id,
    parse_date,
    parse_time,
    rate_limit,
    read_json,
    split_name,
    validate_email,
    validate_name,
    validate_phone,
)

from .models import Appointment, AvailabilitySlot


def appointment_payload(item):
    return {
        "id": item.id,
        "patient_id": item.patient_id,
        "patient_name": item.patient_name,
        "patient_email": item.patient_email,
        "patient_phone": item.patient_phone,
        "doctor": item.doctor_name,
        "service": item.service_name,
        "date": item.appointment_date.isoformat(),
        "time": item.appointment_time.strftime("%H:%M"),
        "notes": item.notes,
        "booking_token": item.booking_token or "",
        "status": item.status,
        "created_by": item.created_by_id or "",
        "manual_booking": item.source in {"manual", "follow_up"},
        "source": item.source,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def availability_payload(item, booked=False, pending_count=0):
    return {
        "id": item.id,
        "doctor": item.doctor_name,
        "date": item.date.isoformat(),
        "time": item.time.strftime("%H:%M"),
        "booked": booked,
        "pending_count": pending_count,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def patient_user(profile):
    return profile.user if profile and profile.user_id else None


def notify_appointment_status(item, label):
    if label in {"Accepted", "Cancelled"}:
        appointment_event(item, "approval" if label == "Accepted" else "cancellation")
    recipient = patient_user(item.patient)
    if recipient:
        create_notification(
            recipient,
            "appointment_status",
            f"Appointment {label.lower()}",
            f"{item.service_name} with {item.doctor_name} on {item.appointment_date.isoformat()} at {item.appointment_time.strftime('%H:%M')} is now {label}.",
            "appointment",
            item.id,
        )


def validate_future_slot(date_value, time_value):
    appointment_date = parse_date(date_value, "appointment date", required=True)
    appointment_time = parse_time(time_value)
    today = dt.date.today()
    if appointment_date < today:
        raise ValueError("Appointment date cannot be in the past.")
    if appointment_date > today + dt.timedelta(days=365):
        raise ValueError("Appointment date must be within one year.")
    appointment_at = dt.datetime.combine(appointment_date, appointment_time)
    if appointment_at <= dt.datetime.now():
        raise ValueError("Choose an appointment time that has not already passed.")
    return appointment_date, appointment_time


@require_http_methods(["GET", "POST", "PATCH", "DELETE"])
def appointments(request):
    if request.method == "GET":
        if not request.user.is_authenticated:
            return api_error("Authentication is required.", 401)
        queryset = Appointment.objects.select_related("patient", "patient__user")
        if request.user.role != "doctor":
            profile = PatientProfile.objects.filter(user=request.user).first()
            queryset = queryset.filter(patient=profile) if profile else queryset.none()
        entries = queryset.order_by("-created_at", "-appointment_date", "-appointment_time")
        return JsonResponse({"appointments": [appointment_payload(item) for item in entries]})

    if not request.user.is_authenticated:
        return api_error("Authentication is required.", 401)
    try:
        payload = read_json(request)
    except ValueError as error:
        return api_error(str(error))
    if request.method == "POST":
        limited = rate_limit(request, "appointments", 10, 10 * 60)
        if limited:
            return limited
        return create_appointment(request, payload)
    if request.method == "PATCH":
        return update_appointment(request, payload)
    return clear_appointments(request, payload)


def create_manual_patient(payload):
    name = validate_name(payload.get("name"), "patient name", 3)
    phone = validate_phone(payload.get("phone"), required=True)
    email = validate_email(payload.get("email"), required=False)
    birthdate = parse_date(payload.get("birthdate"), "birthdate")
    sex = str(payload.get("sex", "")).strip().lower()
    if sex and sex not in {"male", "female", "other", "prefer not to say"}:
        raise ValueError("Choose a valid gender value.")
    if email and (User.objects.filter(email__iexact=email).exists() or PatientProfile.objects.filter(email__iexact=email).exists()):
        raise IntegrityError("duplicate email")
    first_name, middle_name, last_name = split_name(name)
    return PatientProfile.objects.create(
        id=make_id("pat"),
        first_name=first_name,
        middle_name=middle_name,
        last_name=last_name,
        email=email,
        birthdate=birthdate,
        age=calculate_age(birthdate),
        sex=sex,
        phone_number=phone,
        mobile_number=phone,
    )


def create_appointment(request, payload):
    doctor_name = str(payload.get("doctor", "")).strip()
    service_name = str(payload.get("service", "")).strip()
    notes = str(payload.get("notes", "")).strip()[:1000]
    booking_token = str(payload.get("booking_token", "")).strip() or None
    try:
        doctor_name = validate_name(doctor_name, "dentist", 3)
        appointment_date, appointment_time = validate_future_slot(payload.get("date"), payload.get("time"))
    except ValueError as error:
        return api_error(str(error))
    if not Service.objects.filter(name__iexact=service_name).exists():
        return api_error("Choose a valid dental service.")

    is_manual = request.user.role == "doctor"
    if request.user.role not in {"doctor", "patient"}:
        return api_error("This account cannot book appointments.", 403)
    doctor = User.objects.filter(role="doctor", name__iexact=doctor_name, is_active=True).first()
    if is_manual:
        doctor = request.user
        doctor_name = request.user.name
        booking_token = None
    elif not doctor:
        return api_error("Choose a valid clinic dentist.")

    if booking_token:
        existing = Appointment.objects.filter(booking_token=booking_token).first()
        if existing:
            profile = PatientProfile.objects.filter(user=request.user).first()
            if not profile or existing.patient_id != profile.id:
                return api_error("This booking confirmation belongs to another patient account.", 403)
            return JsonResponse({"appointment": appointment_payload(existing), "replayed": True})

    try:
        with transaction.atomic():
            slot = AvailabilitySlot.objects.select_for_update().filter(
                doctor_name__iexact=doctor_name,
                date=appointment_date,
                time=appointment_time,
            ).first()
            if not slot:
                return api_error("That dentist, date, and time are not available. Choose a clinic-approved slot.", 409)
            if Appointment.objects.filter(
                doctor_name__iexact=doctor_name,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                status__in=["approved", "completed"],
            ).exists():
                return api_error("That doctor and time slot are already booked.", 409)

            if is_manual:
                patient_id = str(payload.get("patient_id", "")).strip()
                if patient_id:
                    patient = PatientProfile.objects.filter(id=patient_id).first()
                    if not patient:
                        return api_error("Choose an existing patient.", 404)
                else:
                    patient = create_manual_patient(payload)
            else:
                patient = PatientProfile.objects.filter(user=request.user).first()
                if not patient:
                    return api_error("Your patient profile could not be found.", 400)

            if Appointment.objects.filter(
                patient=patient,
                doctor_name__iexact=doctor_name,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                status__in=["pending", "approved"],
            ).exists():
                return api_error("This patient already has an active appointment for that date and time.", 409)

            source = "manual" if is_manual else "patient"
            if is_manual and (payload.get("source") == "follow_up" or notes.lower().startswith("follow-up")):
                source = "follow_up"
            item = Appointment.objects.create(
                id=make_id("apt"),
                patient=patient,
                doctor=doctor,
                created_by=request.user,
                patient_name=patient.name,
                patient_email=patient.email,
                patient_phone=patient.phone,
                doctor_name=doctor_name,
                service_name=service_name,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                notes=notes,
                booking_token=booking_token,
                status="approved" if is_manual else "pending",
                source=source,
            )
            appointment_event(item)
            cancelled_ids = []
            if is_manual:
                pending = Appointment.objects.filter(
                    doctor_name__iexact=doctor_name,
                    appointment_date=appointment_date,
                    appointment_time=appointment_time,
                    status="pending",
                ).exclude(id=item.id)
                for other in pending.select_related("patient__user"):
                    other.status = "cancelled"
                    other.save(update_fields=["status", "updated_at"])
                    cancelled_ids.append(other.id)
                    notify_appointment_status(other, "Cancelled")
                recipient = patient_user(patient)
                if recipient:
                    create_notification(recipient, "appointment_created", "Appointment scheduled", f"{service_name} with {doctor_name} on {appointment_date.isoformat()} at {appointment_time.strftime('%H:%M')} was scheduled by the clinic.", "appointment", item.id)
            else:
                create_notification(request.user, "appointment_created", "Appointment request submitted", f"{service_name} with {doctor_name} on {appointment_date.isoformat()} at {appointment_time.strftime('%H:%M')} is pending approval.", "appointment", item.id)
                notify_doctors("appointment_created", "New appointment request", f"{request.user.name} requested {service_name} on {appointment_date.isoformat()} at {appointment_time.strftime('%H:%M')}.", "appointment", item.id)
    except IntegrityError:
        return api_error("A patient record or booking already uses the supplied information.", 409)

    response = {"appointment": appointment_payload(item)}
    if is_manual:
        response.update({"patient": {"id": patient.id, "name": patient.name}, "cancelled_appointment_ids": cancelled_ids})
    return JsonResponse(response, status=201)


def update_appointment(request, payload):
    appointment_id = str(payload.get("id", "")).strip()
    status = str(payload.get("status", "")).strip().lower()
    if status not in {"pending", "approved", "completed", "cancelled"}:
        return api_error("Choose a valid status.")
    try:
        with transaction.atomic():
            item = Appointment.objects.select_for_update().select_related("patient__user").get(id=appointment_id)
            if request.user.role == "patient":
                profile = PatientProfile.objects.filter(user=request.user).first()
                if not profile or item.patient_id != profile.id or status != "cancelled":
                    return api_error("Patients can only cancel their own appointment.", 403)
                if item.status not in {"pending", "approved"}:
                    return api_error("Only an active appointment can be cancelled.", 409)
            elif request.user.role != "doctor":
                return api_error("Unauthorized appointment update.", 403)
            if status == "completed" and not item.treatment_records.exists():
                return api_error("Add the patient's treatment record before completing this appointment.", 409)
            if status in {"approved", "completed"} and Appointment.objects.filter(
                doctor_name__iexact=item.doctor_name,
                appointment_date=item.appointment_date,
                appointment_time=item.appointment_time,
                status__in=["approved", "completed"],
            ).exclude(id=item.id).exists():
                return api_error("Another appointment has already been accepted for this dentist and time.", 409)
            previous_status = item.status
            item.status = status
            item.save(update_fields=["status", "updated_at"])
            cancelled_ids = []
            if request.user.role == "doctor" and status == "approved":
                pending = Appointment.objects.filter(
                    doctor_name__iexact=item.doctor_name,
                    appointment_date=item.appointment_date,
                    appointment_time=item.appointment_time,
                    status="pending",
                ).exclude(id=item.id)
                for other in pending.select_related("patient__user"):
                    other.status = "cancelled"
                    other.save(update_fields=["status", "updated_at"])
                    cancelled_ids.append(other.id)
                    notify_appointment_status(other, "Cancelled")
            if status != previous_status:
                label = {"pending": "Pending", "approved": "Accepted", "completed": "Completed", "cancelled": "Cancelled"}[status]
                notify_appointment_status(item, label)
                notify_doctors("appointment_status", "Appointment status updated", f"{item.patient_name}'s {item.service_name} is now {label}.", "appointment", item.id)
    except Appointment.DoesNotExist:
        return api_error("Appointment not found.", 404)
    return JsonResponse({"appointment": appointment_payload(item), "cancelled_appointment_ids": cancelled_ids})


def clear_appointments(request, payload):
    if not doctor_required(request):
        return api_error("Doctor access is required.", 403)
    try:
        dates = sorted({parse_date(value, "appointment date", required=True) for value in str(payload.get("dates", "")).split(",") if value.strip()})
    except ValueError as error:
        return api_error(str(error))
    if not dates:
        return api_error("Select at least one appointment date to clear.")
    if len(dates) > 31 or len({value.strftime("%Y-%m") for value in dates}) != 1:
        return api_error("Select no more than 31 dates from the same month.")
    notify_patients = str(payload.get("notify_patients", "")).lower() == "true"
    message_template = str(payload.get("message", "")).strip()[:200]
    if notify_patients and not message_template:
        message_template = "Your appointment on {date} has been cancelled. Please book a new schedule at your convenience."
    with transaction.atomic():
        entries = list(Appointment.objects.select_for_update().filter(doctor=request.user, appointment_date__in=dates, status__in=["pending", "approved"]).select_related("patient__user"))
        for item in entries:
            item.status = "cancelled"
            item.save(update_fields=["status", "updated_at"])
            if notify_patients and item.patient.user_id:
                message = message_template.replace("{date}", item.appointment_date.isoformat()).replace("{time}", item.appointment_time.strftime("%H:%M")).replace("{service}", item.service_name)
                create_notification(item.patient.user, "appointment_status", "Appointment cancelled", message, "appointment", item.id)
            appointment_event(item, "cancellation")
        slots = AvailabilitySlot.objects.filter(doctor=request.user, date__in=dates)
        removed_ids = list(slots.values_list("id", flat=True))
        slots.delete()
    if not entries and not removed_ids:
        return api_error("No appointments or available time slots were found on the selected dates.", 404)
    return JsonResponse({
        "ok": True,
        "dates": [value.isoformat() for value in dates],
        "cancelled_appointments": [appointment_payload(item) for item in entries],
        "cancelled_appointment_ids": [item.id for item in entries],
        "cancelled_count": len(entries),
        "removed_availability_ids": removed_ids,
        "removed_slot_count": len(removed_ids),
        "notified": notify_patients,
    })


@require_http_methods(["GET", "POST", "PATCH", "DELETE"])
def availability(request):
    if request.method == "GET":
        entries = AvailabilitySlot.objects.filter(date__gte=dt.date.today()).order_by("date", "time", "doctor_name")
        data = []
        for item in entries:
            matching = Appointment.objects.filter(doctor_name__iexact=item.doctor_name, appointment_date=item.date, appointment_time=item.time)
            booked = matching.filter(status__in=["approved", "completed"]).exists()
            if booked and (not request.user.is_authenticated or request.user.role == "patient"):
                continue
            data.append(availability_payload(item, booked, matching.filter(status="pending").count()))
        doctor = User.objects.filter(role="doctor", is_active=True).order_by("date_joined").first()
        return JsonResponse({"availability": data, "clinic_doctor": doctor.name if doctor else ""})
    if not doctor_required(request):
        return api_error("Doctor access is required.", 403)
    try:
        payload = read_json(request)
    except ValueError as error:
        return api_error(str(error))
    if request.method == "POST":
        return create_availability(request, payload)
    availability_id = str(payload.get("id", "")).strip()
    item = AvailabilitySlot.objects.filter(id=availability_id, doctor=request.user).first()
    if not item:
        return api_error("Availability not found.", 404)
    occupied = Appointment.objects.filter(doctor_name__iexact=item.doctor_name, appointment_date=item.date, appointment_time=item.time).exclude(status="cancelled").exists()
    if occupied:
        return api_error("This availability has an appointment and cannot be changed.", 409)
    if request.method == "DELETE":
        item.delete()
        return JsonResponse({"ok": True})
    try:
        date_value, time_value = validate_future_slot(payload.get("date"), payload.get("time"))
    except ValueError as error:
        return api_error(str(error))
    item.date = date_value
    item.time = time_value
    try:
        item.save()
    except IntegrityError:
        return api_error("That dentist availability already exists.", 409)
    return JsonResponse({"availability": availability_payload(item)})


def create_availability(request, payload):
    try:
        if payload.get("dates"):
            dates = sorted({parse_date(value, "availability date", required=True) for value in str(payload["dates"]).split(",") if value.strip()})
            if not dates or len(dates) > 31 or len({value.strftime("%Y-%m") for value in dates}) != 1:
                raise ValueError("Select between 1 and 31 dates from the same month.")
            time_in = parse_time(payload.get("time_in"))
            time_out = parse_time(payload.get("time_out"))
            interval = int(str(payload.get("interval", "30")))
            if interval not in {15, 30, 60}:
                raise ValueError("Appointment interval must be 15, 30, or 60 minutes.")
            start = time_in.hour * 60 + time_in.minute
            end = time_out.hour * 60 + time_out.minute
            if end <= start:
                raise ValueError("Doctor time-out must be later than time-in.")
            times = [dt.time(minute // 60, minute % 60) for minute in range(start, end, interval) if minute + interval <= end]
        else:
            date_value, time_value = validate_future_slot(payload.get("date"), payload.get("time"))
            dates, times = [date_value], [time_value]
        today = dt.date.today()
        if any(value < today or value > today + dt.timedelta(days=365) for value in dates):
            raise ValueError("Availability dates must be between today and one year from now.")
        if len(dates) * len(times) > 1000:
            raise ValueError("The selected schedule creates too many slots. Use a shorter range.")
    except (TypeError, ValueError) as error:
        return api_error(str(error))
    created = []
    skipped = 0
    with transaction.atomic():
        for date_value in dates:
            for time_value in times:
                item, was_created = AvailabilitySlot.objects.get_or_create(
                    doctor_name=request.user.name,
                    date=date_value,
                    time=time_value,
                    defaults={"id": make_id("avail"), "doctor": request.user},
                )
                if was_created:
                    created.append(item)
                else:
                    skipped += 1
    if not created:
        return api_error("All selected dentist, date, and time slots already exist.", 409)
    return JsonResponse({
        "availability": availability_payload(created[0]),
        "availability_created": [availability_payload(item) for item in created],
        "created_count": len(created),
        "skipped_count": skipped,
    }, status=201)
