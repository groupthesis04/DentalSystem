"""Doctor-only, bounded read access to the clinic activity log."""

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from dental_backend.api import api_error, doctor_required

from .audit_models import AuditEvent


@require_GET
def activity_log(request):
    if not doctor_required(request):
        return api_error("Doctor access is required.", 403)

    event = str(request.GET.get("event", "")).strip().upper()
    if event and event not in AuditEvent.Event.values:
        return api_error("Choose a valid activity type.")
    try:
        page = int(request.GET.get("page", "1"))
    except (TypeError, ValueError):
        return api_error("Choose a valid page.")
    if page < 1 or page > 10000:
        return api_error("Choose a valid page.")

    page_size = 25
    entries = AuditEvent.objects.select_related("actor")
    if event:
        entries = entries.filter(event=event)
    total = entries.count()
    start = (page - 1) * page_size
    rows = entries[start:start + page_size]
    return JsonResponse({
        "events": [
            {
                "id": row.id,
                "event": row.event,
                "activity": row.get_event_display(),
                "actor": row.actor_role.title() if row.actor_role else "Unknown",
                "actor_id": row.actor_id_snapshot,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "result": row.result,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    })
