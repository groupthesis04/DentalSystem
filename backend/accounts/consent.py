"""Persist patient consent choices together with their recording context."""

from django.utils import timezone

from .models import PatientConsentRecord


SMS_CONSENT_PURPOSE = (
    "Appointment reminders, follow-up notices, payment reminders, "
    "and clinic-related messages."
)


def sms_consent_status(patient):
    if patient.sms_consent_at is None:
        return "not_recorded"
    if patient.sms_stop_reason:
        return "stopped"
    return "allowed" if patient.sms_consent else "declined"


def record_sms_choice(patient, consent, actor, *, method="", stop_reason="", stop_reason_detail=""):
    """Record a choice or stop, and suppress pending non-test SMS when disabled.

    The caller locks the patient row inside a transaction before this function.
    """
    recorded_at = timezone.now()
    action = (
        PatientConsentRecord.Action.STOPPED if stop_reason
        else PatientConsentRecord.Action.RECORDED
    )
    patient.sms_consent = consent
    patient.sms_consent_at = recorded_at
    patient.sms_consent_method = method
    patient.sms_consent_recorded_by = actor
    patient.sms_stop_reason = stop_reason
    patient.sms_stop_reason_detail = stop_reason_detail
    patient.save(update_fields=[
        "sms_consent", "sms_consent_at", "sms_consent_method", "sms_consent_recorded_by",
        "sms_stop_reason", "sms_stop_reason_detail", "updated_at",
    ])
    PatientConsentRecord.objects.create(
        patient=patient, patient_id_snapshot=patient.pk,
        kind=PatientConsentRecord.Kind.SMS, action=action,
        consent_given=None if stop_reason else consent,
        patient_choice_confirmed=bool(method),
        method=method, purpose=SMS_CONSENT_PURPOSE,
        stop_reason=stop_reason, stop_reason_detail=stop_reason_detail,
        actor=actor, actor_id_snapshot=actor.pk, actor_role=actor.role,
        recorded_at=recorded_at,
    )
    if not consent:
        from communications.models import SmsMessage
        SmsMessage.objects.filter(patient=patient, status="queued", is_test=False).update(
            status="suppressed", error="Patient SMS consent is not active."
        )
