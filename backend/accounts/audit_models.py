"""Durable, deliberately minimal security and clinical activity events."""

from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    class Event(models.TextChoices):
        LOGIN_SUCCESS = "LOGIN_SUCCESS", "Login succeeded"
        LOGIN_FAILED = "LOGIN_FAILED", "Login failed"
        LOGOUT = "LOGOUT", "Logged out"
        PASSWORD_CHANGED = "PASSWORD_CHANGED", "Password changed"
        ACCOUNT_LOCKED = "ACCOUNT_LOCKED", "Account locked"
        ACCOUNT_DISABLED = "ACCOUNT_DISABLED", "Account disabled"
        ACCOUNT_ENABLED = "ACCOUNT_ENABLED", "Account enabled"
        PATIENT_CREATED = "PATIENT_CREATED", "Patient record created"
        PATIENT_UPDATED = "PATIENT_UPDATED", "Patient record updated"
        PATIENT_DELETED = "PATIENT_DELETED", "Patient record deleted"
        SMS_CONSENT_RECORDED = "SMS_CONSENT_RECORDED", "Patient SMS choice recorded"
        SMS_STOPPED = "SMS_STOPPED", "Patient SMS stopped"
        TREATMENT_CREATED = "TREATMENT_CREATED", "Treatment record created"
        TREATMENT_UPDATED = "TREATMENT_UPDATED", "Treatment record updated"
        TREATMENT_DELETED = "TREATMENT_DELETED", "Treatment record deleted"
        APPOINTMENT_CANCELLED = "APPOINTMENT_CANCELLED", "Appointment cancelled"
        SMS_SENT = "SMS_SENT", "SMS accepted by gateway"

    class Result(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    event = models.CharField(max_length=32, choices=Event.choices, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    # Preserve who performed an action if the linked account is later removed.
    actor_id_snapshot = models.CharField(max_length=64, blank=True)
    actor_role = models.CharField(max_length=16, blank=True)
    target_type = models.CharField(max_length=32, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    result = models.CharField(max_length=8, choices=Result.choices)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["actor", "-created_at"], name="audit_actor_date_idx"),
            models.Index(fields=["event", "-created_at"], name="audit_event_date_idx"),
        ]

