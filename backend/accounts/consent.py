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
CLINIC_SMS_BOOKING_NOTICE_VERSION = "clinic-sms-booking-v1"
CLINIC_SMS_STAFF_NOTICE_VERSION = "clinic-sms-staff-v1"
CLINIC_SMS_CONSENT_PURPOSE = (
    "Appointment confirmations, reminders, status/schedule updates, follow-up "
    "care, balance reminders, and other non-promotional messages from BORJA Dental "
    "Clinic to the patient's mobile number."
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
    # Withdrawing consent must not erase an independent clinic safety stop,
    # such as a number known to belong to someone else. The audit record still
    # captures the patient's withdrawal as the action taken now.
    preserve_operational_stop = (
        stop_reason == "patient_withdrew"
        and patient.sms_stop_reason
        and patient.sms_stop_reason != "patient_withdrew"
    )
    profile_stop_reason = patient.sms_stop_reason if preserve_operational_stop else stop_reason
    profile_stop_detail = patient.sms_stop_reason_detail if preserve_operational_stop else stop_reason_detail
    patient.sms_consent = consent
    patient.sms_consent_at = recorded_at
    patient.sms_consent_method = method
    patient.sms_consent_recorded_by = actor
    patient.sms_stop_reason = profile_stop_reason
    patient.sms_stop_reason_detail = profile_stop_detail
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


def record_appointment_sms_choice(
    patient, actor, *, recorded_at, method="booking", clinic_sms_consent=False,
    notice_version="",
):
    """Record separate appointment and optional wider clinic SMS choices.

    The caller locks the patient row and creates the appointment in the same
    transaction. Older clients omit the wider choice and remain limited to
    appointment SMS. A wider choice needs its own explicit checkbox and notice.
    """
    if method != "booking" and method not in STAFF_APPOINTMENT_SMS_METHODS:
        raise ValueError("Choose how the patient agreed to appointment SMS.")
    if type(clinic_sms_consent) is not bool:
        raise ValueError("Choose whether the patient agreed to clinic SMS.")
    broad_notice = (
        CLINIC_SMS_BOOKING_NOTICE_VERSION if method == "booking"
        else CLINIC_SMS_STAFF_NOTICE_VERSION
    )
    if (clinic_sms_consent and notice_version != broad_notice) or (
        not clinic_sms_consent and notice_version
    ):
        raise ValueError("Choose a valid SMS consent notice.")
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
    if clinic_sms_consent:
        PatientConsentRecord.objects.create(
            patient=patient,
            patient_id_snapshot=patient.pk,
            kind=PatientConsentRecord.Kind.SMS,
            action=PatientConsentRecord.Action.RECORDED,
            consent_given=True,
            patient_choice_confirmed=True,
            method=method,
            purpose=CLINIC_SMS_CONSENT_PURPOSE,
            notice_version=notice_version,
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
    # consent_error() keeps legacy bookings scoped to their own appointment.
    # The optional clinic choice alone permits other clinic-related SMS.
    patient.sms_consent_method = (
        "clinic_booking" if method == "booking" else "clinic_staff"
    ) if clinic_sms_consent else "booking"
    patient.sms_consent_recorded_by = actor
    patient.sms_stop_reason = ""
    patient.sms_stop_reason_detail = ""
    patient.save(update_fields=[
        "sms_consent", "sms_consent_at", "sms_consent_method",
        "sms_consent_recorded_by", "sms_stop_reason",
        "sms_stop_reason_detail", "updated_at",
    ])
