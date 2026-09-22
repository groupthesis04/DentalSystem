from django.conf import settings
from django.db import models

from accounts.models import PatientProfile
from scheduling.models import Appointment


class TreatmentRecord(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.SET_NULL,
        related_name="treatment_records",
        null=True,
        blank=True,
    )
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.PROTECT,
        related_name="treatment_records",
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="treatment_records",
        null=True,
        blank=True,
    )
    patient_name = models.CharField(max_length=120)
    doctor_name = models.CharField(max_length=120)
    treatment_date = models.DateField()
    tooth_numbers = models.CharField(max_length=120, blank=True)
    procedure = models.CharField(max_length=120)
    amount_charged = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=24, default="unpaid")
    diagnosis = models.TextField(blank=True)
    treatment = models.TextField(blank=True)
    prescription = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    remarks = models.TextField(blank=True)
    next_visit = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    legacy_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["patient", "treatment_date"], name="record_patient_date_idx"),
            models.Index(fields=["payment_status"], name="record_payment_status_idx"),
        ]

    def __str__(self):
        return f"{self.patient_name} - {self.procedure}"
