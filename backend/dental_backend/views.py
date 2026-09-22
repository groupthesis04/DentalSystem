import logging

from django.db import connection
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from records.models import TreatmentRecord
from scheduling.models import Appointment

from .api import api_error, doctor_required


logger = logging.getLogger(__name__)


def csrf_failure(request, reason=""):
    # Keep the user-facing response generic, but put Django's exact rejection
    # reason in Railway logs so deployment problems can be diagnosed safely.
    logger.warning(
        "CSRF rejected path=%s host=%s origin=%s reason=%s",
        request.path,
        request.get_host(),
        request.headers.get("Origin", ""),
        reason,
    )
    return api_error("Security token expired. Refresh the page and try again.", 403)


@require_GET
def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse({"ok": True, "backend": "django", "database": "mysql"})


@require_GET
def reports(request):
    if not doctor_required(request):
        return api_error("Doctor access is required.", 403)

    statuses = {
        row["status"]: row["total"]
        for row in Appointment.objects.values("status").annotate(total=Count("id"))
    }
    money = TreatmentRecord.objects.aggregate(
        charged=Sum("amount_charged"),
        paid=Sum("amount_paid"),
        balance=Sum("balance"),
    )
    return JsonResponse(
        {
            "appointments": {
                "total": Appointment.objects.count(),
                "by_status": statuses,
            },
            "treatments": {
                "total": TreatmentRecord.objects.count(),
                "amount_charged": float(money["charged"] or 0),
                "amount_paid": float(money["paid"] or 0),
                "balance": float(money["balance"] or 0),
            },
        }
    )
