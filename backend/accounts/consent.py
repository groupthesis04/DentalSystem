"""Persist patient consent choices together with their recording context."""

from django.utils import timezone

from .models import PatientConsentRecord


SMS_CONSENT_PURPOSE = (
    "Appointment reminders, follow-up notices, payment reminders, "
    "and clinic-related messages."
)
APPOINTMENT_SMS_CONSENT_PURPOSE = (
    "Appointment confirmations, reminders, and appointment status and schedule "
    "updates sent by BORJA Dental Clinic to the mobile number registered to "
    "the patient's account."
)
STAFF_APPOINTMENT_SMS_CONSENT_PURPOSE = (
    "Appointment confirmations, reminders, and appointment status and schedule "
    "updates sent by BORJA Dental Clinic to the mobile number the patient "
    "provided to the clinic."
)
APPOINTMENT_SMS_NOTICE_VERSION = "appointment-booking-v1"
STAFF_APPOINTMENT_SMS_NOTICE_VERSION = "appointment-staff-v1"
STAFF_APPOINTMENT_SMS_METHODS = frozenset({"staff_in_person", "staff_phone"})


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


def record_appointment_sms_choice(patient, actor, *, recorded_at, method="booking"):
    """Record an appointment choice without broadening its SMS purpose.

    The caller locks the patient row and creates the appointment in the same
    transaction. An existing broader grant remains broad; a prior patient
    withdrawal is replaced by this fresh, narrower affirmative choice.
    """
    if method != "booking" and method not in STAFF_APPOINTMENT_SMS_METHODS:
        raise ValueError("Choose how the patient agreed to appointment SMS.")
    PatientConsentRecord.objects.create(
        patient=patient,
        patient_id_snapshot=patient.pk,
        kind=PatientConsentRecord.Kind.SMS,
        action=PatientConsentRecord.Action.RECORDED,
        consent_given=True,
        patient_choice_confirmed=True,
        method=method,
        purpose=(
            APPOINTMENT_SMS_CONSENT_PURPOSE if method == "booking"
            else STAFF_APPOINTMENT_SMS_CONSENT_PURPOSE
        ),
        notice_version=(
            APPOINTMENT_SMS_NOTICE_VERSION if method == "booking"
            else STAFF_APPOINTMENT_SMS_NOTICE_VERSION
        ),
        actor=actor,
        actor_id_snapshot=actor.pk,
        actor_role=actor.role,
        recorded_at=recorded_at,
    )
    # A separate operational stop (for example, a wrong number) must not be
    # cleared by a booking checkbox. It does not prevent the appointment.
    if patient.sms_stop_reason and patient.sms_stop_reason != "patient_withdrew":
        return
    broad_grant_active = (
        patient.sms_consent is True
        and patient.sms_consent_at is not None
        and not patient.sms_stop_reason
        and patient.sms_consent_method != "booking"
    )
    if broad_grant_active:
        return

    patient.sms_consent = True
    patient.sms_consent_at = recorded_at
    # All appointment-only grants keep the same scope in consent_error(), even
    # when the evidence records that a staff member heard the patient's choice.
    patient.sms_consent_method = "booking"
    patient.sms_consent_recorded_by = actor
    patient.sms_stop_reason = ""
    patient.sms_stop_reason_detail = ""
    patient.save(update_fields=[
        "sms_consent", "sms_consent_at", "sms_consent_method",
        "sms_consent_recorded_by", "sms_stop_reason",
        "sms_stop_reason_detail", "updated_at",
    ])
