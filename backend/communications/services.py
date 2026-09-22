from dental_backend.api import make_id

from accounts.models import User

from .models import Notification


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


def notify_doctors(notification_type, title, message, entity_type="", entity_id=""):
    for doctor in User.objects.filter(role="doctor", is_active=True):
        create_notification(
            doctor,
            notification_type,
            title,
            message,
            entity_type,
            entity_id,
        )
