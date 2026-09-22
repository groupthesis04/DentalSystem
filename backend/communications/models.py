from django.conf import settings
from django.db import models


class Notification(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(max_length=40)
    title = models.CharField(max_length=120)
    message = models.TextField()
    entity_type = models.CharField(max_length=40, blank=True)
    entity_id = models.CharField(max_length=64, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    legacy_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["recipient", "is_read", "created_at"], name="notification_recipient_idx")
        ]

    def __str__(self):
        return self.title


class Message(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_messages",
    )
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    legacy_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["sender", "recipient", "created_at"], name="message_conversation_idx")
        ]

    def __str__(self):
        return f"{self.sender} to {self.recipient}"


class SmsRule(models.Model):
    key = models.CharField(primary_key=True, max_length=32)
    enabled = models.BooleanField(default=True)
    template = models.TextField()
    active_template = models.ForeignKey("SmsTemplate", null=True, blank=True, on_delete=models.SET_NULL, related_name="active_for_rules")
    delay_minutes = models.PositiveSmallIntegerField(default=0)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)


class SmsTemplate(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    rule = models.ForeignKey(SmsRule, on_delete=models.PROTECT, related_name="templates")
    name = models.CharField(max_length=100)
    body = models.TextField()
    delay_minutes = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class SmsMessage(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    event_key = models.CharField(max_length=180, unique=True)
    rule = models.ForeignKey(SmsRule, on_delete=models.PROTECT)
    patient = models.ForeignKey("accounts.PatientProfile", null=True, blank=True, on_delete=models.SET_NULL)
    appointment = models.ForeignKey("scheduling.Appointment", null=True, blank=True, on_delete=models.SET_NULL)
    record = models.ForeignKey("records.TreatmentRecord", null=True, blank=True, on_delete=models.SET_NULL)
    patient_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=24, blank=True)
    body = models.TextField()
    context = models.JSONField(default=dict)
    is_test = models.BooleanField(default=False)
    status = models.CharField(max_length=24, default="queued")
    provider_id = models.CharField(max_length=80, null=True, blank=True, unique=True)
    error = models.CharField(max_length=300, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    scheduled_for = models.DateTimeField()
    expires_at = models.DateTimeField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["status", "scheduled_for"], name="sms_queue_idx")]


class SmsBalanceSchedule(models.Model):
    patient = models.OneToOneField("accounts.PatientProfile", primary_key=True, on_delete=models.CASCADE)
    next_due_at = models.DateTimeField(null=True, blank=True)


class SmsWorker(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    last_run_at = models.DateTimeField(null=True, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)
    lease_token = models.CharField(max_length=64, blank=True)
