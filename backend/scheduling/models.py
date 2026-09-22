from django.conf import settings
from django.db import models

from accounts.models import PatientProfile


class Appointment(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    SOURCE_CHOICES = [
        ("patient", "Patient"),
        ("manual", "Manual"),
        ("follow_up", "Follow-up"),
    ]

    id = models.CharField(primary_key=True, max_length=64)
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="doctor_appointments",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_appointments",
        null=True,
        blank=True,
    )
    patient_name = models.CharField(max_length=120)
    patient_email = models.EmailField(blank=True)
    patient_phone = models.CharField(max_length=24, blank=True)
    doctor_name = models.CharField(max_length=120)
    service_name = models.CharField(max_length=120)
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="pending")
    source = models.CharField(max_length=24, choices=SOURCE_CHOICES, default="patient")
    notes = models.TextField(blank=True)
    booking_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    legacy_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["patient", "appointment_date"], name="appt_patient_date_idx"),
            models.Index(fields=["doctor", "appointment_date", "appointment_time"], name="appt_doctor_slot_idx"),
            models.Index(fields=["status", "appointment_date"], name="appt_status_date_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["pending", "approved", "completed", "cancelled"]),
                name="appointment_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(source__in=["patient", "manual", "follow_up"]),
                name="appointment_source_valid",
            ),
        ]

    def __str__(self):
        return f"{self.patient_name} - {self.appointment_date} {self.appointment_time}"


class AvailabilitySlot(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="availability_slots",
        null=True,
        blank=True,
    )
    doctor_name = models.CharField(max_length=120)
    date = models.DateField()
    time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    legacy_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["doctor_name", "date", "time"],
                name="unique_doctor_availability",
            )
        ]
        indexes = [models.Index(fields=["date", "time"], name="availability_date_time_idx")]

    def __str__(self):
        return f"{self.doctor_name} - {self.date} {self.time}"
