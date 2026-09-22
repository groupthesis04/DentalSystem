from django.conf import settings
from django.db import models


class Service(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    name = models.CharField(max_length=120, unique=True)
    description = models.CharField(max_length=500)
    detail_tagline = models.CharField(max_length=240, blank=True)
    detail_items = models.TextField(blank=True)
    detail_duration = models.CharField(max_length=80, blank=True)
    detail_audience = models.CharField(max_length=80, blank=True)
    detail_care_note = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    legacy_payload = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.name


class Promotion(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    title = models.CharField(max_length=120)
    description = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    legacy_payload = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.title


class Feedback(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedback_entries",
    )
    name = models.CharField(max_length=80)
    rating = models.PositiveSmallIntegerField(default=5)
    message = models.CharField(max_length=500)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="edited_feedback_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    legacy_payload = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.name} - {self.rating}/5"
