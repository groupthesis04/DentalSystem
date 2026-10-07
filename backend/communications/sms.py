import datetime as dt
import string
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from accounts.audit import record_audit_event
from accounts.models import PatientProfile
from dental_backend.api import make_id
from records.models import TreatmentRecord
from scheduling.models import Appointment

from . import sms_provider
from .models import SmsBalanceSchedule, SmsMessage, SmsRule, SmsTemplate, SmsWorker
from .services import notify_doctors, notify_due_next_visits, notify_upcoming_appointments


RULES = {
    "booking": ("Appointment Booking Confirmation", "When a patient books an appointment", "Hi {PatientName}, your appointment request at {ClinicName} for {AppointmentDate} at {Time} was received and is pending approval."),
    "approval": ("Appointment Approval Message", "When admin accepts an appointment", "Hi {PatientName}, your appointment at {ClinicName} on {AppointmentDate} at {Time} has been approved. We look forward to seeing you."),
    "appointment_reminder": ("Appointment Reminder", "About 24 hours before an accepted appointment", "Hi {PatientName}, this is a reminder of your appointment at {ClinicName} on {AppointmentDate} at {Time}. We look forward to seeing you."),
    "walk_in": ("Walk-in Appointment Message", "When admin adds a walk-in appointment", "Hi {PatientName}, the clinic has scheduled your appointment at {ClinicName} on {AppointmentDate} at {Time}. Thank you."),
    "next_visit": ("Next Visit Reminder", "When admin assigns a next visit", "Hi {PatientName}, your next visit at {ClinicName} is on {AppointmentDate}. Time: {Time}. Please contact the clinic with any questions."),
    "balance": ("Balance Reminder Every 7 Days", "While the patient has an outstanding balance", "Hi {PatientName}, this is a reminder from {ClinicName} that your current balance is PHP {Balance}. Please contact the clinic about payment. Thank you."),
    "cancellation": ("Appointment Cancellation Notice", "When an appointment is cancelled", "Hi {PatientName}, your appointment at {ClinicName} on {AppointmentDate} at {Time} has been cancelled. Please contact the clinic to arrange another visit."),
}
PLACEHOLDERS = ["PatientName", "AppointmentDate", "Time", "Balance", "ClinicName"]
TEMPLATE_NAMES = {
    "booking": "Appointment Booked", "approval": "Appointment Approved",
    "appointment_reminder": "Appointment Reminder",
    "walk_in": "Walk-in Appointment Added", "next_visit": "Next Visit Reminder",
    "balance": "Payment Reminder", "cancellation": "Appointment Cancelled",
}
MANUAL_RULE_KEY = "manual"


def ensure_rules():
    for key, (_, _, template) in RULES.items():
        rule, _ = SmsRule.objects.get_or_create(key=key, defaults={"template": template})
        if not rule.active_template_id:
            with transaction.atomic():
                rule = SmsRule.objects.select_for_update().get(pk=key)
                if not rule.active_template_id:
                    saved = SmsTemplate.objects.create(id=make_id("smst"), rule=rule, name=TEMPLATE_NAMES[key], body=rule.template, delay_minutes=rule.delay_minutes)
                    rule.active_template = saved
                    rule.save(update_fields=["active_template"])


def validate_template(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 1000:
        raise ValueError("Message content must contain 1 to 1,000 characters.")
    value = value.strip()
    if value.upper().startswith("TEST"):
        raise ValueError("Semaphore ignores messages beginning with TEST. Start with your clinic name or a greeting.")
    try:
        for _, field, spec, conversion in string.Formatter().parse(value):
            if field is not None and (field not in PLACEHOLDERS or spec or conversion):
                raise ValueError("Use only the available placeholders, without formatting expressions.")
    except ValueError:
        raise ValueError("Invalid placeholder. Available placeholders: " + ", ".join("{" + key + "}" for key in PLACEHOLDERS)) from None
    return value


def patient_balance(patient):
    return TreatmentRecord.objects.filter(patient=patient, balance__gt=0).aggregate(total=Sum("balance"))["total"] or Decimal("0")


def message_context(patient, date=None, time=None):
    return {
        "PatientName": patient.name,
        "AppointmentDate": date.strftime("%b %d, %Y") if date else "not assigned",
        "Time": time.strftime("%I:%M %p") if time else "to be confirmed",
        "Balance": f"{patient_balance(patient):,.2f}",
        "ClinicName": settings.SMS_CLINIC_NAME,
    }


def enqueue(key, patient, event_key, context, *, appointment=None, record=None, phone=None, is_test=False):
    ensure_rules()
    rule = SmsRule.objects.get(pk=key)
    now = timezone.now()
    number = phone if phone is not None else patient.phone or (patient.user.phone if patient.user_id else "")
    state, error = ("queued", "") if rule.enabled or is_test else ("suppressed", "Automation was off when this event occurred.")
    if not is_test:
        choice = PatientProfile.objects.filter(pk=patient.pk).values_list(
            "sms_consent", "sms_consent_at", "sms_stop_reason"
        ).first()
        if not choice or choice[0] is not True or choice[1] is None or choice[2]:
            state, error = "suppressed", "Patient SMS consent is not active."
    try:
        number = sms_provider.normalize_phone(number)
    except ValueError as exc:
        if state == "queued":
            state, error = "failed", str(exc)
    item, created = SmsMessage.objects.get_or_create(event_key=event_key, defaults={
        "id": make_id("sms"), "rule": rule, "patient": patient, "appointment": appointment,
        "record": record, "patient_name": context["PatientName"], "phone": number,
        "body": rule.template.format_map(context), "context": context, "status": state,
        "error": error, "is_test": is_test, "scheduled_for": now + dt.timedelta(minutes=0 if is_test else rule.delay_minutes),
        "expires_at": now + dt.timedelta(hours=24),
    })
    if created and item.status == "failed":
        notify_sms_failure(item)
    return item


def ensure_manual_rule():
    # Manual clinic messages have a rule only to fit the existing SMS queue.
    # This key is intentionally absent from RULES and the automation controls.
    rule, _ = SmsRule.objects.get_or_create(
        key=MANUAL_RULE_KEY, defaults={"template": "", "enabled": True}
    )
    return rule


def enqueue_manual(patient, event_key, template, *, body=None, rule=None, actor=None):
    """Queue one clinic-composed message through the existing SMS worker."""
    rule = rule or ensure_manual_rule()
    now = timezone.now()
    context = message_context(patient)
    context["ManualTemplate"] = template
    context["ManualSenderId"] = actor.pk if actor else ""
    if body is None:
        body = template.format_map(context)
    number = patient.phone or (patient.user.phone if patient.user_id else "")
    if patient.sms_consent is not True or patient.sms_consent_at is None or patient.sms_stop_reason:
        state, error = "suppressed", "Patient SMS consent is not active."
    else:
        state, error = "queued", ""
    try:
        number = sms_provider.normalize_phone(number)
    except ValueError as exc:
        if state == "queued":
            state, error = "failed", str(exc)
    context["ManualAccepted"] = state == "queued"
    context["ManualSkipReason"] = error if state != "queued" else ""
    item, created = SmsMessage.objects.get_or_create(event_key=event_key, defaults={
        "id": make_id("sms"), "rule": rule, "patient": patient,
        "patient_name": patient.name, "phone": number, "body": body,
        "context": context, "status": state, "error": error,
        "scheduled_for": now, "expires_at": now + dt.timedelta(hours=24),
    })
    if created and item.status == "failed":
        notify_sms_failure(item)
    return item


def notify_sms_failure(item):
    notify_doctors(
        "sms_delivery_failure",
        "SMS delivery failed",
        f"An SMS for {item.patient_name} failed. Check the SMS message logs.",
        "sms",
        item.id,
        preference_key="sms_delivery_failure",
    )


def appointment_event(item, key=None):
    key = key or {"patient": "booking", "manual": "walk_in", "follow_up": "next_visit"}[item.source]
    if key == "cancellation":
        SmsMessage.objects.filter(appointment=item, status="queued").update(status="suppressed", error="Appointment was cancelled.")
    event = f"appointment:{item.id}:{key}"
    if key in {"approval", "cancellation"}:
        event += ":" + item.updated_at.isoformat()
    return enqueue(key, item.patient, event, message_context(item.patient, item.appointment_date, item.appointment_time), appointment=item)


def record_next_visit(item, previous_date, defer=False):
    if item.next_visit != previous_date:
        SmsMessage.objects.filter(record=item, rule_id="next_visit", status="queued").update(status="suppressed", error="Next visit date was changed.")
    if item.next_visit and item.next_visit != previous_date and not defer:
        enqueue("next_visit", item.patient, f"record:{item.id}:next_visit:{item.updated_at.isoformat()}", message_context(item.patient, item.next_visit), record=item)


def sync_balance(patient, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        schedule, _ = SmsBalanceSchedule.objects.get_or_create(patient=patient)
        schedule = SmsBalanceSchedule.objects.select_for_update().get(pk=schedule.pk)
        if patient_balance(patient) <= 0:
            schedule.next_due_at = None
            SmsMessage.objects.filter(patient=patient, rule_id="balance", status="queued").update(status="suppressed", error="Balance fully paid.")
        elif schedule.next_due_at is None:
            schedule.next_due_at = now + dt.timedelta(days=7)
        schedule.save(update_fields=["next_due_at"])


def queue_due_balances(now):
    # Seed existing unpaid balances once; partial payments do not restart the clock.
    ids = set(TreatmentRecord.objects.filter(balance__gt=0).values_list("patient_id", flat=True))
    ids.update(SmsBalanceSchedule.objects.filter(next_due_at__isnull=False).values_list("patient_id", flat=True))
    for patient in PatientProfile.objects.filter(id__in=ids):
        sync_balance(patient, now)
    for schedule_id in SmsBalanceSchedule.objects.filter(next_due_at__lte=now).values_list("pk", flat=True):
        with transaction.atomic():
            schedule = SmsBalanceSchedule.objects.select_for_update().select_related("patient").get(pk=schedule_id)
            if not schedule.next_due_at or schedule.next_due_at > now:
                continue
            enqueue("balance", schedule.patient, f"balance:{schedule.pk}:{schedule.next_due_at.isoformat()}", message_context(schedule.patient))
            notify_doctors(
                "payment_balance_reminder", "Balance reminder due",
                f"A payment reminder is due for {schedule.patient.name}.",
                "patient", schedule.patient_id, preference_key="payment_balance_reminder",
            )
            schedule.next_due_at = now + dt.timedelta(days=7)
            schedule.save(update_fields=["next_due_at"])


def queue_upcoming_patient_reminders(now):
    """Queue one patient SMS when an accepted appointment enters the next 24 hours."""
    deadline = now + dt.timedelta(hours=24)
    for appointment in Appointment.objects.filter(
        status="approved",
        appointment_date__gte=timezone.localdate(now),
        appointment_date__lte=timezone.localdate(deadline),
    ).select_related("patient__user"):
        visit_at = timezone.make_aware(dt.datetime.combine(appointment.appointment_date, appointment.appointment_time))
        if not now < visit_at <= deadline:
            continue
        event_key = (
            f"appointment:{appointment.pk}:appointment_reminder:"
            f"{appointment.appointment_date.isoformat()}:{appointment.appointment_time.isoformat()}"
        )
        enqueue(
            "appointment_reminder", appointment.patient, event_key,
            message_context(appointment.patient, appointment.appointment_date, appointment.appointment_time),
            appointment=appointment,
        )


def suppression_reason(item, now):
    if item.expires_at <= now:
        return "Unsent message expired after 24 hours."
    if item.is_test:
        return ""
    if item.rule_id != MANUAL_RULE_KEY and not item.rule.enabled:
        return "Automation is turned off."
    if not item.patient_id:
        return "Patient record is no longer available."
    if item.patient.sms_consent is not True or item.patient.sms_consent_at is None or item.patient.sms_stop_reason:
        return "Patient SMS consent is not active."
    if item.rule_id == "balance" and patient_balance(item.patient) <= 0:
        return "Balance fully paid."
    if item.rule_id in {"booking", "approval", "appointment_reminder", "walk_in", "cancellation"} and not item.appointment_id:
        return "Appointment is no longer available."
    if item.appointment:
        if item.rule_id == "appointment_reminder":
            if (item.context.get("AppointmentDate") != item.appointment.appointment_date.strftime("%b %d, %Y")
                    or item.context.get("Time") != item.appointment.appointment_time.strftime("%I:%M %p")):
                return "Appointment schedule changed since this reminder was queued."
        if item.rule_id != "cancellation":
            visit_at = timezone.make_aware(dt.datetime.combine(item.appointment.appointment_date, item.appointment.appointment_time))
            if visit_at <= now:
                return "Appointment time has already passed."
        expected = {"booking": {"pending"}, "approval": {"approved"}, "appointment_reminder": {"approved"}, "walk_in": {"approved"}, "next_visit": {"approved"}, "cancellation": {"cancelled"}}
        if item.appointment.status not in expected.get(item.rule_id, set()):
            return "Appointment status has changed since this message was queued."
    if item.rule_id == "next_visit" and not item.appointment_id:
        if not item.record or not item.record.next_visit or item.record.next_visit.strftime("%b %d, %Y") != item.context["AppointmentDate"]:
            return "Next visit is no longer assigned to this date."
        if item.record.next_visit < timezone.localdate(now):
            return "Next visit date has already passed."
    return ""


def dispatch(item_id, now):
    claimed = SmsMessage.objects.filter(pk=item_id, status="queued").update(status="processing", updated_at=now)
    if not claimed:
        return
    # Serialize a send with consent changes for this patient. An opt-out that
    # completes before this lock is acquired suppresses the send; one that waits
    # for an in-flight send completes only after the provider call has finished.
    with transaction.atomic():
        item = SmsMessage.objects.select_related("rule", "patient__user", "appointment", "record").get(pk=item_id)
        if item.patient_id:
            item.patient = PatientProfile.objects.select_for_update().get(pk=item.patient_id)
        reason = suppression_reason(item, now)
        if reason:
            item.status, item.error = "suppressed", reason
            item.save()
            return
        if not item.is_test:
            item.phone = item.patient.phone or (item.patient.user.phone if item.patient.user_id else "")
            item.context["Balance"] = f"{patient_balance(item.patient):,.2f}"
            item.context["PatientName"] = item.patient.name
            item.context["ClinicName"] = settings.SMS_CLINIC_NAME
            if item.rule_id != MANUAL_RULE_KEY:
                item.body = item.rule.template.format_map(item.context)
        item.attempts += 1
        try:
            item.phone = sms_provider.normalize_phone(item.phone)
            item.provider_id, item.status = sms_provider.send(item.phone, item.body)
            item.submitted_at = now
            item.checked_at = now
            item.error = f"{sms_provider.name()} rejected the message. Check its message log." if item.status in {"failed", "refunded"} else ""
        except ValueError as exc:
            item.status, item.error = "failed", str(exc)
        except sms_provider.SmsProviderError as exc:
            item.status = "unknown" if exc.uncertain else "failed"
            item.error = str(exc)
            if exc.retryable and item.attempts < 3:
                item.status = "queued"
                item.scheduled_for = now + dt.timedelta(minutes=1)
        item.save()
        if item.provider_id and item.status in {"submitted", "pending", "sent"}:
            record_audit_event("SMS_SENT", target=item, metadata={"origin": "system"})
        if item.status in {"failed", "refunded"}:
            notify_sms_failure(item)


def process_queue():
    now = timezone.now()
    ensure_rules()
    SmsWorker.objects.get_or_create(pk=1)
    token = uuid.uuid4().hex
    acquired = SmsWorker.objects.filter(pk=1).filter(Q(lease_until__isnull=True) | Q(lease_until__lt=now)).update(lease_until=now + dt.timedelta(minutes=5), lease_token=token, last_run_at=now)
    if not acquired:
        return 0
    count = 0
    try:
        # A crashed send may have reached the provider; never automatically resend it.
        SmsMessage.objects.filter(status="processing", updated_at__lt=now - dt.timedelta(minutes=5)).update(status="unknown", error="Worker stopped during sending. Check provider logs before resending.")
        queue_due_balances(now)
        queue_upcoming_patient_reminders(now)
        notify_upcoming_appointments(now)
        notify_due_next_visits(now)
        SmsMessage.objects.filter(status="queued", expires_at__lte=now).update(status="expired", error="Unsent message expired after 24 hours.")
        due_ids = (
            list(SmsMessage.objects.filter(status="queued", scheduled_for__lte=now)
                 .order_by("scheduled_for").values_list("pk", flat=True)[:5])
            if sms_provider.ready() else []
        )
        for item_id in due_ids:
            dispatch(item_id, now)
            count += 1
        # Only Semaphore's numeric IDs can be queried here. Preserve messages
        # submitted through former providers without assuming they were unsent.
        SmsMessage.objects.filter(
            status__in=["submitted", "pending"], provider_id__isnull=False,
        ).exclude(provider_id__regex=r"^[0-9]+$").update(
            status="unknown",
            error="Status cannot be refreshed with Semaphore. Check original provider logs; this message has not been resent.",
            checked_at=now,
            updated_at=now,
        )
        waiting = SmsMessage.objects.filter(status__in=["submitted", "pending"], provider_id__regex=r"^[0-9]+$").filter(Q(checked_at__isnull=True) | Q(checked_at__lte=now - dt.timedelta(minutes=1))).order_by("checked_at")[:5]
        for item in waiting:
            previous_status = item.status
            try:
                _, item.status = sms_provider.status(item.provider_id)
                item.error = "Semaphore rejected the message. Check its message log." if item.status in {"failed", "refunded"} else ""
            except sms_provider.SmsProviderError:
                item.error = "Status refresh unavailable; the message has not been resent."
            item.checked_at = now
            item.save(update_fields=["status", "error", "checked_at", "updated_at"])
            if previous_status not in {"failed", "refunded"} and item.status in {"failed", "refunded"}:
                notify_sms_failure(item)
        return count
    finally:
        SmsWorker.objects.filter(pk=1, lease_token=token).update(lease_until=None, lease_token="")
