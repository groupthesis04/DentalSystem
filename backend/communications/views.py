from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from accounts.models import User
from dental_backend.api import api_error, doctor_required, make_id, rate_limit, read_json, user_payload
from dental_backend.realtime import schedule_dashboard_change

from .models import DOCTOR_NOTIFICATION_KEYS, DoctorNotificationPreference, Message, Notification


def notification_payload(item):
    return {
        "id": item.id,
        "recipient_id": item.recipient_id,
        "type": item.notification_type,
        "title": item.title,
        "message": item.message,
        "entity_type": item.entity_type,
        "entity_id": item.entity_id,
        "read": item.is_read,
        "read_at": item.read_at.isoformat() if item.read_at else "",
        "created_at": item.created_at.isoformat(),
    }


@require_http_methods(["GET", "PATCH"])
def notifications(request):
    if not request.user.is_authenticated:
        return api_error("Authentication is required.", 401)

    if request.method == "GET":
        entries = Notification.objects.filter(recipient=request.user).order_by("-created_at")[:50]
        data = [notification_payload(item) for item in entries]
        return JsonResponse(
            {
                "notifications": data,
                "unread_count": sum(not item["read"] for item in data),
            }
        )

    try:
        payload = read_json(request)
    except ValueError as error:
        return api_error(str(error))

    queryset = Notification.objects.filter(recipient=request.user, is_read=False)
    if str(payload.get("mark_all", "")).lower() not in {"1", "true", "yes"}:
        notification_id = str(payload.get("id", "")).strip()
        if not notification_id:
            return api_error("Choose a notification to update.")
        queryset = queryset.filter(id=notification_id)
    updated = queryset.update(is_read=True, read_at=timezone.now())
    if not updated and payload.get("id"):
        exists = Notification.objects.filter(id=payload["id"], recipient=request.user).exists()
        if not exists:
            return api_error("Notification not found.", 404)
    return JsonResponse({"ok": True, "updated_count": updated})


@require_http_methods(["GET", "PATCH"])
def notification_preferences(request):
    if not doctor_required(request):
        return api_error("Doctor access is required.", 403)
    preferences = DoctorNotificationPreference.objects.filter(user=request.user).first()
    if request.method == "PATCH":
        try:
            payload = read_json(request)
        except ValueError as error:
            return api_error(str(error))
        changes = payload.get("preferences")
        if not isinstance(changes, dict) or not changes or any(
            key not in DOCTOR_NOTIFICATION_KEYS or type(value) is not bool
            for key, value in changes.items()
        ):
            return api_error("Choose valid notification settings.")
        if preferences is None:
            preferences = DoctorNotificationPreference(user=request.user)
        for key, value in changes.items():
            setattr(preferences, key, value)
        preferences.save()
    values = {
        key: getattr(preferences, key) if preferences else True
        for key in DOCTOR_NOTIFICATION_KEYS
    }
    return JsonResponse({"preferences": values})


def message_payload(item):
    return {
        "id": item.id,
        "sender_id": item.sender_id,
        "recipient_id": item.recipient_id,
        "sender_name": item.sender.name,
        "recipient_name": item.recipient.name,
        "body": item.body,
        "message": item.body,
        "read": item.is_read,
        "read_at": item.read_at.isoformat() if item.read_at else "",
        "created_at": item.created_at.isoformat(),
    }


@require_http_methods(["GET", "POST"])
def messages(request):
    if not request.user.is_authenticated:
        return api_error("Authentication is required.", 401)

    if request.method == "GET":
        entries = Message.objects.filter(
            Q(sender=request.user) | Q(recipient=request.user)
        ).select_related("sender", "recipient").order_by("created_at")
        contacts = User.objects.filter(is_active=True).exclude(id=request.user.id)
        if request.user.role == "patient":
            contacts = contacts.filter(role="doctor")
        else:
            contacts = contacts.filter(role="patient")
        return JsonResponse(
            {
                "messages": [message_payload(item) for item in entries],
                "contacts": [user_payload(item) for item in contacts.order_by("name")],
            }
        )

    try:
        payload = read_json(request)
    except ValueError as error:
        return api_error(str(error))
    limited = rate_limit(request, "messages", 30, 60)
    if limited:
        return limited
    recipient_id = str(payload.get("recipient_id", "")).strip()
    body = str(payload.get("body", payload.get("message", ""))).strip()
    if not body or len(body) > 1000:
        return api_error("Message must contain between 1 and 1000 characters.")
    try:
        recipient = User.objects.get(id=recipient_id, is_active=True)
    except User.DoesNotExist:
        return api_error("Message recipient not found.", 404)
    if recipient.id == request.user.id or recipient.role == request.user.role:
        return api_error("Messages must be between a patient and clinic staff.", 403)
    item = Message.objects.create(
        id=make_id("msg"),
        sender=request.user,
        recipient=recipient,
        body=body,
    )
    if request.user.role == "patient":
        schedule_dashboard_change()
    return JsonResponse({"message": message_payload(item)}, status=201)
