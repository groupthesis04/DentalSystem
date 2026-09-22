import datetime as dt

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from accounts.models import PatientProfile
from clinic.models import Service
from communications.services import create_notification, notify_doctors
from communications.sms import record_next_visit, sync_balance
from dental_backend.api import (
    api_error,
    doctor_required,
    make_id,
    parse_date,
    parse_money,
    read_json,
)
from scheduling.models import Appointment

from .models import TreatmentRecord


def record_payload(item):
    return {
        "id": item.id,
        "appointment_id": item.appointment_id or "",
        "patient_id": item.patient_id,
        "patient_name": item.patient_name,
        "doctor_id": item.doctor_id or "",
        "doctor_name": item.doctor_name,
        "treatment_date": item.treatment_date.isoformat(),
        "tooth_numbers": item.tooth_numbers,
        "procedure": item.procedure,
        "amount_charged": float(item.amount_charged),
        "amount_paid": float(item.amount_paid),
        "balance": float(item.balance),
        "payment_status": item.payment_status,
        "diagnosis": item.diagnosis,
        "treatment": item.treatment or item.procedure,
        "prescription": item.prescription,
        "notes": item.notes,
        "remarks": item.remarks,
        "next_visit": item.next_visit.isoformat() if item.next_visit else "",
        "status": "completed",
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def validate_record_payload(payload):
    procedure = str(payload.get("procedure", payload.get("treatment", ""))).strip()
    diagnosis = str(payload.get("diagnosis", "")).strip()
    tooth_numbers = str(payload.get("tooth_numbers", "")).strip()
    if not procedure:
        raise ValueError("Procedure or service is required.")
    if not diagnosis:
        raise ValueError("Diagnosis or clinical findings are required.")
    if len(tooth_numbers) > 120 or any(char not in "0123456789#,.- /" for char in tooth_numbers):
        raise ValueError("Enter valid tooth numbers separated by commas.")
    treatment_date = parse_date(payload.get("treatment_date"), "treatment date", required=True)
    next_visit = parse_date(payload.get("next_visit"), "next visit")
    if treatment_date > dt.date.today():
        raise ValueError("Treatment date cannot be in the future.")
    if next_visit and next_visit < treatment_date:
        raise ValueError("Next visit cannot be before the treatment date.")
    amount_charged = parse_money(payload.get("amount_charged", 0), "Amount charged")
    amount_paid = parse_money(payload.get("amount_paid", 0), "Amount paid")
    if amount_paid > amount_charged:
        raise ValueError("Amount paid cannot exceed amount charged.")
    return {
        "procedure": procedure[:120],
        "diagnosis": diagnosis[:700],
        "tooth_numbers": tooth_numbers,
        "treatment_date": treatment_date,
        "next_visit": next_visit,
        "amount_charged": amount_charged,
        "amount_paid": amount_paid,
        "balance": amount_charged - amount_paid,
        "payment_status": "completed" if amount_charged - amount_paid <= 0 else "unpaid",
        "prescription": str(payload.get("prescription", "")).strip()[:700],
        "remarks": str(payload.get("remarks", payload.get("notes", ""))).strip()[:1000],
    }


@require_http_methods(["GET", "POST", "PATCH", "DELETE"])
def records(request):
    if not request.user.is_authenticated:
        return api_error("Authentication is required.", 401)
    if request.method == "GET":
        queryset = TreatmentRecord.objects.select_related("patient", "patient__user", "doctor")
        if request.user.role != "doctor":
            profile = PatientProfile.objects.filter(user=request.user).first()
            queryset = queryset.filter(patient=profile) if profile else queryset.none()
        queryset = queryset.order_by("-treatment_date", "-created_at")
        return JsonResponse({"records": [record_payload(item) for item in queryset]})
    if not doctor_required(request):
        return api_error("Doctor access is required.", 403)
    try:
        payload = read_json(request)
    except ValueError as error:
        return api_error(str(error))
    if request.method == "DELETE":
        return delete_record(request, payload)
    return save_record(request, payload, editing=request.method == "PATCH")


def save_record(request, payload, editing=False):
    try:
        values = validate_record_payload(payload)
    except ValueError as error:
        return api_error(str(error))
    if not Service.objects.filter(name__iexact=values["procedure"]).exists():
        return api_error("Choose a valid dental service.")
    appointment_id = str(payload.get("appointment_id", "")).strip()
    patient_id = str(payload.get("patient_id", "")).strip()
    with transaction.atomic():
        item = None
        if editing:
            item = TreatmentRecord.objects.select_for_update().filter(id=str(payload.get("id", "")).strip()).first()
            if not item:
                return api_error("Treatment record not found.", 404)
        appointment = None
        if appointment_id:
            appointment = Appointment.objects.select_for_update().filter(id=appointment_id).first()
            if not appointment:
                return api_error("Appointment not found.", 404)
            patient = appointment.patient
        else:
            patient = PatientProfile.objects.filter(id=patient_id or (item.patient_id if item else "")).first()
        if not patient:
            return api_error("Choose a valid patient.")
        if appointment and item is None and TreatmentRecord.objects.filter(appointment=appointment).exists():
            return api_error("This appointment already has a treatment record.", 409)

        previous_next_visit = item.next_visit if item else None
        if item is None:
            item = TreatmentRecord(id=make_id("rec"))
        item.appointment = appointment
        item.patient = patient
        item.doctor = request.user
        item.patient_name = patient.name
        item.doctor_name = request.user.name
        item.treatment_date = values["treatment_date"]
        item.tooth_numbers = values["tooth_numbers"]
        item.procedure = values["procedure"]
        item.amount_charged = values["amount_charged"]
        item.amount_paid = values["amount_paid"]
        item.balance = values["balance"]
        item.payment_status = values["payment_status"]
        item.diagnosis = values["diagnosis"]
        item.treatment = values["procedure"]
        item.prescription = values["prescription"]
        item.notes = values["remarks"]
        item.remarks = values["remarks"]
        item.next_visit = values["next_visit"]
        item.save()
        sync_balance(patient)
        record_next_visit(item, previous_next_visit, defer=payload.get("schedule_follow_up") is True)
        if appointment:
            appointment.status = "completed"
            appointment.save(update_fields=["status", "updated_at"])

        if patient.user_id:
            notification_type = "treatment_updated" if editing else "treatment_created"
            title = "Treatment record updated" if editing else "Treatment record added"
            create_notification(
                patient.user,
                notification_type,
                title,
                f"{item.procedure} was recorded with PHP {item.amount_paid:,.2f} paid and PHP {item.balance:,.2f} remaining.",
                "treatment",
                item.id,
            )
        notify_doctors(
            "treatment_updated" if editing else "treatment_created",
            "Treatment transaction updated" if editing else "Treatment transaction recorded",
            f"{item.procedure} was recorded for {patient.name} with a balance of PHP {item.balance:,.2f}.",
            "treatment",
            item.id,
        )
    return JsonResponse({"record": record_payload(item)}, status=200 if editing else 201)


def delete_record(request, payload):
    item = TreatmentRecord.objects.select_related("patient__user").filter(id=str(payload.get("id", "")).strip()).first()
    if not item:
        return api_error("Treatment record not found.", 404)
    patient_user = item.patient.user if item.patient.user_id else None
    procedure = item.procedure
    patient_name = item.patient_name
    item_id = item.id
    patient = item.patient
    item.delete()
    sync_balance(patient)
    if patient_user:
        create_notification(patient_user, "treatment_deleted", "Treatment record removed", f"The {procedure} record was removed by clinic staff.", "treatment", item_id)
    notify_doctors("treatment_deleted", "Treatment transaction removed", f"The {procedure} record for {patient_name} was removed.", "treatment", item_id)
    return JsonResponse({"ok": True})
