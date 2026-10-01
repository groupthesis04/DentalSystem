import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_patient_consent"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "event",
                    models.CharField(
                        choices=[
                            ("LOGIN_SUCCESS", "Login succeeded"),
                            ("LOGIN_FAILED", "Login failed"),
                            ("LOGOUT", "Logged out"),
                            ("PASSWORD_CHANGED", "Password changed"),
                            ("ACCOUNT_LOCKED", "Account locked"),
                            ("ACCOUNT_DISABLED", "Account disabled"),
                            ("ACCOUNT_ENABLED", "Account enabled"),
                            ("PATIENT_CREATED", "Patient record created"),
                            ("PATIENT_UPDATED", "Patient record updated"),
                            ("PATIENT_DELETED", "Patient record deleted"),
                            ("TREATMENT_CREATED", "Treatment record created"),
                            ("TREATMENT_UPDATED", "Treatment record updated"),
                            ("TREATMENT_DELETED", "Treatment record deleted"),
                            ("APPOINTMENT_CANCELLED", "Appointment cancelled"),
                            ("SMS_SENT", "SMS accepted by gateway"),
                        ],
                        db_index=True,
                        max_length=32,
                    ),
                ),
                ("actor_id_snapshot", models.CharField(blank=True, max_length=64)),
                ("actor_role", models.CharField(blank=True, max_length=16)),
                ("target_type", models.CharField(blank=True, max_length=32)),
                ("target_id", models.CharField(blank=True, max_length=64)),
                (
                    "result",
                    models.CharField(
                        choices=[("success", "Success"), ("failed", "Failed")],
                        max_length=8,
                    ),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(fields=["actor", "-created_at"], name="audit_actor_date_idx"),
                    models.Index(fields=["event", "-created_at"], name="audit_event_date_idx"),
                ],
            },
        ),
    ]
