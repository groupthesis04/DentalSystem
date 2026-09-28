import datetime as dt
import uuid

from django.utils import timezone

from dental_backend.api import make_id

from accounts.models import User
from records.models import TreatmentRecord
from scheduling.models import Appointment

from .models import DoctorNotificationPreference, Notification


def create_notification(
    recipient,
    notification_type,
    title,
    message,
    entity_type="",
    entity_id="",
):
    if not recipient:
        return None
    return Notification.objects.create(
        id=make_id("ntf"),
        recipient=recipient,
        notification_type=notification_type,
        title=title[:120],
        message=message[:1000],
        entity_type=entity_type[:40],
        entity_id=entity_id[:64],
    )


def notify_doctors(notification_type, title, message, entity_type="", entity_id="", *, preference_key=None):
    for doctor in User.objects.filter(role="doctor", is_active=True):
        if preference_key and DoctorNotificationPreference.objects.filter(
            user=doctor, **{preference_key: False}
        ).exists():
            continue
        create_notification(
            doctor,
            notification_type,
            title,
            message,
            entity_type,
            entity_id,
        )


def notify_upcoming_appointments(now=None):
    """Create one doctor dashboard alert per approved appointment slot within 24 hours.

    The stable notification ID makes repeated worker passes safe, including after a
    restart or concurrent worker run. This never enqueues a patient SMS.
    """
    now = now or timezone.now()
    deadline = now + dt.timedelta(hours=24)
    doctor_ids = list(User.objects.filter(role="doctor", is_active=True).values_list("pk", flat=True))
    if not doctor_ids:
        return 0
    opted_out = set(DoctorNotificationPreference.objects.filter(
        user_id__in=doctor_ids,
        upcoming_appointment_reminder=False,
    ).values_list("user_id", flat=True))
    appointments = Appointment.objects.filter(
        status="approved",
        appointment_date__range=(timezone.localdate(now), timezone.localdate(deadline)),
    ).order_by("appointment_date", "appointment_time")
    created_count = 0
    for appointment in appointments:
        appointment_at = timezone.make_aware(
            dt.datetime.combine(appointment.appointment_date, appointment.appointment_time),
            timezone.get_current_timezone(),
        )
        if not now < appointment_at <= deadline:
            continue
        when = timezone.localtime(appointment_at).strftime("%B %d, %Y at %I:%M %p")
        for doctor_id in doctor_ids:
            if doctor_id in opted_out:
                continue
            event_key = (
                f"doctor-upcoming:{doctor_id}:{appointment.pk}:"
                f"{appointment.appointment_date.isoformat()}:{appointment.appointment_time.isoformat()}"
            )
            notification_id = f"ntf_{uuid.uuid5(uuid.NAMESPACE_URL, event_key).hex}"
            _, created = Notification.objects.get_or_create(
                id=notification_id,
                defaults={
                    "recipient_id": doctor_id,
                    "notification_type": "upcoming_appointment_reminder",
                    "title": "Upcoming appointment reminder",
                    "message": (
                        f"{appointment.patient_name}'s {appointment.service_name} appointment "
                        f"is scheduled for {when}."
                    ),
                    "entity_type": "appointment",
                    "entity_id": appointment.pk,
                },
            )
            created_count += created
    return created_count


def notify_due_next_visits(now=None):
    """Alert doctors on the clinic-local due date of a recorded next visit."""
    now = now or timezone.now()
    today = timezone.localdate(now)
    doctor_ids = list(User.objects.filter(role="doctor", is_active=True).values_list("pk", flat=True))
    if not doctor_ids:
        return 0
    opted_out = set(DoctorNotificationPreference.objects.filter(
        user_id__in=doctor_ids,
        next_visit=False,
    ).values_list("user_id", flat=True))
    created_count = 0
    for record in TreatmentRecord.objects.filter(next_visit=today):
        for doctor_id in doctor_ids:
            if doctor_id in opted_out:
                continue
            event_key = f"doctor-next-visit:{doctor_id}:{record.pk}:{today.isoformat()}"
            notification_id = f"ntf_{uuid.uuid5(uuid.NAMESPACE_URL, event_key).hex}"
            _, created = Notification.objects.get_or_create(
                id=notification_id,
                defaults={
                    "recipient_id": doctor_id,
                    "notification_type": "next_visit",
                    "title": "Next visit due today",
                    "message": f"{record.patient_name}'s next visit is due today ({today:%B %d, %Y}).",
                    "entity_type": "treatment",
                    "entity_id": record.pk,
                },
            )
            created_count += created
    return created_count
