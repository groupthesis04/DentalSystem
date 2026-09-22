import datetime as dt
import hashlib
import uuid

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from dental_backend.api import api_error, doctor_required, make_id, rate_limit, read_json

from . import sms_provider
from .models import SmsMessage, SmsRule, SmsTemplate, SmsWorker
from .sms import PLACEHOLDERS, RULES, enqueue, ensure_rules, message_context, suppression_reason, validate_template


# Keep provider states for diagnostics while grouping the clinic-facing filters.
STATUS_GROUPS = {
    "pending": ("queued", "processing", "submitted", "pending", "unknown"),
    "sent": ("sent",),
    "delivered": ("delivered",),
    "failed": ("failed", "refunded"),
    "not_sent": ("suppressed", "expired"),
}
DISPLAY_STATUSES = {status: group for group, statuses in STATUS_GROUPS.items() for status in statuses}


def semaphore_credit_payload():
    payload = {
        "credit_balance": None,
        "credit_status": "not_configured",
        "credit_checked_at": None,
        "credit_error": "",
    }
    if not settings.SEMAPHORE_API_KEY:
        return payload

    key_digest = hashlib.sha256(settings.SEMAPHORE_API_KEY.encode("utf-8")).hexdigest()[:16]
    cache_key = f"communications:semaphore-account:{key_digest}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    checked_at = timezone.now()
    try:
        account = sms_provider.account()
        payload.update(
            credit_balance=float(account["credit_balance"]),
            credit_status=account["status"] or "available",
            credit_checked_at=checked_at.isoformat(),
        )
        cache_seconds = max(60, int(getattr(settings, "SEMAPHORE_ACCOUNT_CACHE_SECONDS", 60)))
    except sms_provider.SmsProviderError as exc:
        payload.update(
            credit_status="unavailable",
            credit_checked_at=checked_at.isoformat(),
            credit_error=str(exc),
        )
        # Semaphore limits account requests to two per minute.
        cache_seconds = 30
    cache.set(cache_key, payload, cache_seconds)
    return payload


def rule_payload(rule):
    name, trigger, _ = RULES[rule.key]
    frequency = "Every 7 days until fully paid" if rule.key == "balance" else "Immediately"
    if rule.delay_minutes:
        frequency = f"{frequency}; {rule.delay_minutes}-minute delay" if rule.key == "balance" else f"After {rule.delay_minutes} minutes"
    return {"key": rule.key, "name": name, "trigger": trigger, "frequency": frequency, "enabled": rule.enabled, "template": rule.template, "updated_at": rule.updated_at.isoformat()}


def resend_block_reason(item, resend_id=""):
    if resend_id:
        return "A new attempt already exists for this message."
    if item.status not in STATUS_GROUPS["failed"]:
        return "Only confirmed failed messages can be resent. Pending or uncertain messages must not be duplicated."
    if not sms_provider.ready():
        return "Semaphore is not connected. SMS delivery is inactive."
    reason = suppression_reason(item, timezone.now())
    if reason:
        return reason
    phone = item.phone if item.is_test else item.patient.phone or (item.patient.user.phone if item.patient.user_id else "")
    try:
        sms_provider.normalize_phone(phone)
    except ValueError as exc:
        return str(exc)
    return ""


def message_payload(item, resend_id=""):
    reason = resend_block_reason(item, resend_id)
    source = "test" if item.is_test else "manual" if item.event_key.startswith("resend:") else "automated"
    return {
        "id": item.pk, "rule": item.rule_id, "name": RULES[item.rule_id][0],
        "trigger": RULES[item.rule_id][1], "source": source,
        "patient_name": item.patient_name, "phone": item.phone, "body": item.body,
        "status": item.status, "display_status": DISPLAY_STATUSES.get(item.status, "pending"),
        "error": item.error, "provider_id": item.provider_id, "is_test": item.is_test,
        "created_at": item.created_at.isoformat(), "scheduled_for": item.scheduled_for.isoformat(),
        "submitted_at": item.submitted_at.isoformat() if item.submitted_at else None,
        "checked_at": item.checked_at.isoformat() if item.checked_at else None,
        "can_resend": not reason, "resend_reason": reason, "resend_id": resend_id or None,
        "resend_of": item.event_key.removeprefix("resend:") if item.event_key.startswith("resend:") else None,
    }


@require_http_methods(["GET"])
def dashboard(request):
    if not doctor_required(request):
        return api_error("Doctor access is required.", 403)
    ensure_rules()
    rules = {rule.key: rule for rule in SmsRule.objects.all()}
    queryset = SmsMessage.objects.all()
    today = timezone.localdate()
    month = queryset.filter(created_at__gte=timezone.now() - dt.timedelta(days=30), is_test=False)
    sent = month.filter(status="sent").count()
    decided = month.filter(status__in=["sent", "failed", "refunded"]).count()
    worker = SmsWorker.objects.filter(pk=1).first()
    last_run = worker.last_run_at if worker else None
    credit = semaphore_credit_payload()
    return JsonResponse({
        "rules": [rule_payload(rules[key]) for key in RULES],
        "placeholders": PLACEHOLDERS,
        "provider": {"name": "Semaphore", "ready": sms_provider.ready(), "sending_enabled": settings.SMS_ENABLED, "key_configured": bool(settings.SEMAPHORE_API_KEY), "sender_name": settings.SEMAPHORE_SENDER_NAME or "Account default", "worker_active": bool(last_run and last_run > timezone.now() - dt.timedelta(minutes=3)), "last_run_at": last_run.isoformat() if last_run else None, **credit},
        "stats": {"active": sum(rule.enabled for rule in rules.values()), "sent_today": queryset.filter(status="sent", submitted_at__date=today).count(), "pending": queryset.filter(status__in=["queued", "processing", "submitted", "pending"]).count(), "success_rate": round(sent * 100 / decided) if decided else None},
        "clinic_name": settings.SMS_CLINIC_NAME,
    })


@require_http_methods(["PATCH"])
def rules(request):
    if not doctor_required(request):
        return api_error("Doctor access is required.", 403)
    ensure_rules()
    try:
        payload = read_json(request)
        key = payload.get("key")
        enabled = payload.get("enabled")
        if "enabled" in payload and not isinstance(enabled, bool):
            raise ValueError("Enabled must be true or false.")
        if not isinstance(key, str) or (key not in RULES and key != "all"):
            raise ValueError("Choose a valid automation rule.")
        template = validate_template(payload["template"]) if "template" in payload else None
        if key == "all" and (template is not None or enabled is None):
            raise ValueError("Bulk changes can only enable or disable automations.")
        if template is None and enabled is None:
            raise ValueError("Provide a template or automation status.")
    except ValueError as exc:
        return api_error(str(exc))
    with transaction.atomic():
        items = SmsRule.objects.select_for_update()
        if key != "all":
            items = items.filter(pk=key)
        for item in items:
            if enabled is not None:
                item.enabled = enabled
            if template is not None:
                item.template = template
                saved = item.active_template
                saved.body = template
                saved.save(update_fields=["body", "updated_at"])
            item.updated_by = request.user
            item.save()
            if enabled is False:
                SmsMessage.objects.filter(rule=item, status="queued", is_test=False).update(status="suppressed", error="Automation was turned off by an administrator.")
    return JsonResponse({"ok": True})


def template_payload(item):
    active = item.rule.active_template_id == item.pk
    return {
        "id": item.pk, "rule": item.rule_id, "name": item.name, "body": item.body,
        "enabled": item.rule.enabled and active, "active": active, "can_delete": not active,
        "delay_minutes": item.delay_minutes, "trigger": RULES[item.rule_id][1],
        "updated_at": item.updated_at.isoformat(),
    }


@require_http_methods(["GET", "POST", "PATCH", "DELETE"])
def templates(request):
    if not doctor_required(request):
        return api_error("Doctor access is required.", 403)
    ensure_rules()
    if request.method == "GET":
        items = SmsTemplate.objects.select_related("rule").order_by("created_at", "id")
        return JsonResponse({"templates": [template_payload(item) for item in items], "placeholders": PLACEHOLDERS, "clinic_name": settings.SMS_CLINIC_NAME})
    try:
        payload = read_json(request)
        name = payload.get("name")
        if "name" in payload and (not isinstance(name, str) or not name.strip() or len(name.strip()) > 100):
            raise ValueError("Template name must contain 1 to 100 characters.")
        body = validate_template(payload["body"]) if "body" in payload else None
        delay = payload.get("delay_minutes")
        if "delay_minutes" in payload and (type(delay) is not int or delay not in (0, 5, 15, 30, 60)):
            raise ValueError("Choose an available send delay.")
        enabled = payload.get("enabled")
        if "enabled" in payload and not isinstance(enabled, bool):
            raise ValueError("Template status must be true or false.")
        if request.method == "POST":
            key = payload.get("rule")
            if not isinstance(key, str) or key not in RULES:
                raise ValueError("Choose a valid automation rule.")
            if name is None or body is None:
                raise ValueError("Template name and message content are required.")
        else:
            template_id = payload.get("id")
            if not isinstance(template_id, str):
                raise ValueError("Choose a valid template.")
            existing = SmsTemplate.objects.filter(pk=template_id).first()
            if not existing:
                return api_error("Template not found.", 404)
            key = existing.rule_id
    except ValueError as exc:
        return api_error(str(exc))
    with transaction.atomic():
        # Lock the owning rule so two activations cannot cause duplicate active templates.
        rule = SmsRule.objects.select_for_update().get(pk=key)
        if request.method == "POST":
            item = SmsTemplate(id=make_id("smst"), rule=rule)
        else:
            item = SmsTemplate.objects.select_for_update().filter(pk=template_id).first()
            if not item:
                return api_error("Template not found.", 404)
        if request.method == "DELETE":
            if rule.active_template_id == item.pk:
                return api_error("Activate another template for this automation before deleting this one.", 409)
            deleted_id = item.pk
            item.delete()
            return JsonResponse({"ok": True, "id": deleted_id})
        if name is not None:
            item.name = name.strip()
        if body is not None:
            item.body = body
        if delay is not None:
            item.delay_minutes = delay
        item.save()
        if enabled is True:
            rule.active_template = item
            rule.enabled = True
        elif enabled is False and rule.active_template_id == item.pk:
            rule.enabled = False
            SmsMessage.objects.filter(rule=rule, status="queued", is_test=False).update(status="suppressed", error="Template was turned off by an administrator.")
        if rule.active_template_id == item.pk:
            rule.template = item.body
            rule.delay_minutes = item.delay_minutes
            rule.updated_by = request.user
            rule.save()
        item.rule = rule
    return JsonResponse({"template": template_payload(item)}, status=201 if request.method == "POST" else 200)


@require_http_methods(["GET"])
def logs(request):
    if not doctor_required(request):
        return api_error("Doctor access is required.", 403)
    try:
        page = max(1, int(request.GET.get("page", 1)))
        page_size = int(request.GET.get("page_size", 10))
        if page_size not in (10, 25, 50):
            raise ValueError("Choose 10, 25, or 50 rows per page.")
        start = dt.date.fromisoformat(request.GET["date_from"]) if request.GET.get("date_from") else None
        end = dt.date.fromisoformat(request.GET["date_to"]) if request.GET.get("date_to") else None
        if start and end and start > end:
            raise ValueError("The start date must be on or before the end date.")
        start_at = timezone.make_aware(dt.datetime.combine(start, dt.time.min)).astimezone(dt.timezone.utc) if start else None
        end_at = timezone.make_aware(dt.datetime.combine(end, dt.time.max)).astimezone(dt.timezone.utc) if end else None
    except (ValueError, OverflowError):
        return api_error("Choose valid page settings and a valid date range.")
    queryset = SmsMessage.objects.all()
    status = request.GET.get("status", "")
    if status:
        if status not in STATUS_GROUPS and status not in DISPLAY_STATUSES:
            return api_error("Choose a valid delivery status.")
        queryset = queryset.filter(status__in=STATUS_GROUPS.get(status, (status,)))
    key = request.GET.get("rule", "")
    if key:
        if key not in RULES:
            return api_error("Choose a valid message type.")
        queryset = queryset.filter(rule_id=key)
    search = request.GET.get("q", "").strip()[:120]
    if search:
        phone_search = "".join(char for char in search if char.isdecimal())
        match = Q(patient_name__icontains=search) | Q(phone__icontains=search)
        if len(phone_search) >= 4:
            match |= Q(phone__icontains=phone_search.lstrip("0"))
        queryset = queryset.filter(match)
    source = request.GET.get("source", "")
    if source == "test":
        queryset = queryset.filter(is_test=True)
    elif source == "manual":
        queryset = queryset.filter(is_test=False, event_key__startswith="resend:")
    elif source == "automated":
        queryset = queryset.filter(is_test=False).exclude(event_key__startswith="resend:")
    elif source:
        return api_error("Choose a valid message source.")
    if start_at:
        queryset = queryset.filter(created_at__gte=start_at)
    if end_at:
        # Include the entire final day in the clinic's time zone.
        queryset = queryset.filter(created_at__lte=end_at)
    stats = queryset.aggregate(
        total=Count("pk"), delivered=Count("pk", filter=Q(status="delivered")),
        failed=Count("pk", filter=Q(status__in=STATUS_GROUPS["failed"])),
        scheduled=Count("pk", filter=Q(status="queued", scheduled_for__gt=timezone.now())),
    )
    ensure_rules()
    stats["active_rules"] = SmsRule.objects.filter(enabled=True).count()
    stats["total_rules"] = len(RULES)
    total = stats["total"]
    pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, pages)
    items = list(queryset.select_related("rule", "patient__user", "appointment", "record").order_by("-created_at", "-id")[(page-1)*page_size:page*page_size])
    resend_ids = dict(SmsMessage.objects.filter(event_key__in=["resend:" + item.pk for item in items]).values_list("event_key", "pk"))
    return JsonResponse({
        "messages": [message_payload(item, resend_ids.get("resend:" + item.pk, "")) for item in items],
        "total": total, "page": page, "pages": pages, "page_size": page_size, "stats": stats,
    })


@require_http_methods(["POST"])
def resend(request):
    if not doctor_required(request):
        return api_error("Doctor access is required.", 403)
    limited = rate_limit(request, "resend_sms", 5, 60)
    if limited:
        return limited
    try:
        payload = read_json(request)
        message_id = payload.get("id")
        if not isinstance(message_id, str) or not message_id:
            raise ValueError("Choose a message to resend.")
    except ValueError as exc:
        return api_error(str(exc))
    with transaction.atomic():
        original = SmsMessage.objects.select_for_update().filter(pk=message_id).first()
        if not original:
            return api_error("Message not found.", 404)
        # Each attempt has one successor. Retries of this request cannot send twice.
        event_key = "resend:" + original.pk
        existing = SmsMessage.objects.filter(event_key=event_key).first()
        if existing:
            return JsonResponse({"message": message_payload(existing), "already_queued": True})
        reason = resend_block_reason(original)
        if reason:
            return api_error(reason, 409)
        if original.is_test:
            context = original.context.copy()
        elif original.appointment_id:
            context = message_context(original.patient, original.appointment.appointment_date, original.appointment.appointment_time)
        else:
            context = message_context(original.patient, original.record.next_visit if original.record_id and original.rule_id == "next_visit" else None)
        item = enqueue(original.rule_id, original.patient, event_key, context,
                       appointment=original.appointment, record=original.record,
                       phone=original.phone if original.is_test else None, is_test=original.is_test)
        if original.is_test:
            item.body = original.body
            item.save(update_fields=["body"])
    return JsonResponse({"message": message_payload(item), "already_queued": False}, status=201)


@require_http_methods(["POST"])
def test_sms(request):
    if not doctor_required(request):
        return api_error("Doctor access is required.", 403)
    limited = rate_limit(request, "test_sms", 3, 60)
    if limited:
        return limited
    if not sms_provider.ready():
        return api_error("SMS delivery is inactive. Configure Semaphore on the server first.", 409)
    try:
        payload = read_json(request)
        key = payload.get("key")
        if not isinstance(key, str) or key not in RULES:
            raise ValueError("Choose an automation rule.")
        phone = sms_provider.normalize_phone(payload.get("phone"))
        template = validate_template(payload.get("template"))
    except ValueError as exc:
        return api_error(str(exc))
    context = {"PatientName": "Sample Patient", "AppointmentDate": timezone.localdate().strftime("%b %d, %Y"), "Time": "09:00 AM", "Balance": "500.00", "ClinicName": settings.SMS_CLINIC_NAME}
    with transaction.atomic():
        item = enqueue(key, None, "test:" + uuid.uuid4().hex, context, phone=phone, is_test=True)
        item.body = template.format_map(context)
        item.save(update_fields=["body"])
    return JsonResponse({"message": message_payload(item)}, status=201)
