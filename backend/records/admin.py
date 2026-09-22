from django.contrib import admin

from .models import TreatmentRecord


@admin.register(TreatmentRecord)
class TreatmentRecordAdmin(admin.ModelAdmin):
    list_display = ("patient_name", "procedure", "treatment_date", "amount_paid", "balance", "payment_status")
    list_filter = ("payment_status", "treatment_date")
    search_fields = ("patient_name", "procedure", "diagnosis")
