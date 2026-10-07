from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from dental_backend.api import api_error, doctor_required, make_id, rate_limit, read_json, validate_name

from .models import Feedback, Promotion, Service


SERVICE_DETAIL_LIMITS = {
    "detail_tagline": 240,
    "detail_items": 1600,
    "detail_duration": 80,
    "detail_audience": 80,
    "detail_care_note": 100,
}


def service_payload(item):
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "detail_tagline": item.detail_tagline,
        "detail_items": item.detail_items,
        "detail_duration": item.detail_duration,
        "detail_audience": item.detail_audience,
        "detail_care_note": item.detail_care_note,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def promo_payload(item):
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def feedback_payload(item):
    return {
        "id": item.id,
        "name": item.name,
        "rating": item.rating,
        "message": item.message,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def service_details(payload):
    details = {}
    for field, limit in SERVICE_DETAIL_LIMITS.items():
        value = str(payload.get(field, "")).strip()
        if field == "detail_items":
            items = [line.strip() for line in value.splitlines() if line.strip()]
            if len(items) > 12 or any(len(item) > 180 for item in items):
                raise ValueError("The Learn More list can contain up to 12 short items.")
            value = "\n".join(items)
        details[field] = value[:limit]
    return details


@require_http_methods(["GET", "POST", "PATCH", "DELETE"])
def services(request):
    if request.method == "GET":
        entries = Service.objects.order_by("created_at", "name")
        return JsonResponse({"services": [service_payload(item) for item in entries]})
    if not doctor_required(request):
        return api_error("Doctor access is required.", 403)
    try:
        payload = read_json(request)
    except ValueError as error:
        return api_error(str(error))

    if request.method == "DELETE":
        deleted, _ = Service.objects.filter(id=str(payload.get("id", "")).strip()).delete()
        return JsonResponse({"ok": True}) if deleted else api_error("Service not found.", 404)

    name = str(payload.get("name", "")).strip()
    description = str(payload.get("description", "")).strip()
    if len(name) < 3:
        return api_error("Service name must be at least 3 characters.")
    if len(description) < 10:
        return api_error("Service description must be at least 10 characters.")
    try:
        details = service_details(payload)
        if request.method == "POST":
            item = Service.objects.create(
                id=make_id("svc"),
                name=name[:120],
                description=description[:500],
                **details,
            )
            status = 201
        else:
            try:
                item = Service.objects.get(id=str(payload.get("id", "")).strip())
            except Service.DoesNotExist:
                return api_error("Service not found.", 404)
            item.name = name[:120]
            item.description = description[:500]
            for field, value in details.items():
                setattr(item, field, value)
            item.save()
            status = 200
    except IntegrityError:
        return api_error("A service with that name already exists.", 409)
    except ValueError as error:
        return api_error(str(error))
    return JsonResponse({"service": service_payload(item)}, status=status)


@require_http_methods(["GET", "POST", "PATCH", "DELETE"])
def promos(request):
    if request.method == "GET":
        entries = Promotion.objects.order_by("created_at")
        return JsonResponse({"promos": [promo_payload(item) for item in entries]})
    if not doctor_required(request):
        return api_error("Doctor access is required.", 403)
    try:
        payload = read_json(request)
    except ValueError as error:
        return api_error(str(error))
    if request.method == "DELETE":
        deleted, _ = Promotion.objects.filter(id=str(payload.get("id", "")).strip()).delete()
        return JsonResponse({"ok": True}) if deleted else api_error("Promo not found.", 404)
    title = str(payload.get("title", "")).strip()
    description = str(payload.get("description", "")).strip()
    if len(title) < 3 or len(description) < 10:
        return api_error("Enter a promo title and a description of at least 10 characters.")
    if request.method == "POST":
        item = Promotion.objects.create(id=make_id("promo"), title=title[:120], description=description[:500])
        status = 201
    else:
        try:
            item = Promotion.objects.get(id=str(payload.get("id", "")).strip())
        except Promotion.DoesNotExist:
            return api_error("Promo not found.", 404)
        item.title = title[:120]
        item.description = description[:500]
        item.save()
        status = 200
    return JsonResponse({"promo": promo_payload(item)}, status=status)


@require_http_methods(["GET", "POST", "PATCH", "DELETE"])
def feedback(request):
    if request.method == "GET":
        entries = Feedback.objects.order_by("-created_at")
        return JsonResponse({"feedback": [feedback_payload(item) for item in entries]})
    try:
        payload = read_json(request)
    except ValueError as error:
        return api_error(str(error))
    if request.method in {"PATCH", "DELETE"} and not doctor_required(request):
        return api_error("Doctor access is required.", 403)
    if request.method == "POST":
        limited = rate_limit(request, "feedback", 5, 10 * 60)
        if limited:
            return limited
    if request.method == "DELETE":
        deleted, _ = Feedback.objects.filter(id=str(payload.get("id", "")).strip()).delete()
        return JsonResponse({"ok": True}) if deleted else api_error("Feedback not found.", 404)
    try:
        rating = int(payload.get("rating", 5))
    except (TypeError, ValueError):
        rating = 0
    message = str(payload.get("message", "")).strip()
    if rating not in range(1, 6):
        return api_error("Choose a rating from 1 to 5.")
    if len(message) < 10:
        return api_error("Feedback must be at least 10 characters.")
    if request.method == "POST":
        try:
            name = request.user.name if request.user.is_authenticated else validate_name(payload.get("name") or "Clinic Visitor")
        except ValueError as error:
            return api_error(str(error))
        item = Feedback.objects.create(
            id=make_id("fb"),
            author=request.user if request.user.is_authenticated else None,
            name=name[:80],
            rating=rating,
            message=message[:500],
        )
        status = 201
    else:
        try:
            item = Feedback.objects.get(id=str(payload.get("id", "")).strip())
        except Feedback.DoesNotExist:
            return api_error("Feedback not found.", 404)
        item.rating = rating
        item.message = message[:500]
        item.updated_by = request.user
        item.save()
        status = 200
    return JsonResponse({"feedback": feedback_payload(item)}, status=status)
