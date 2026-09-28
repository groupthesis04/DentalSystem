from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("communications", "0003_sms_template_library"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DoctorNotificationPreference",
            fields=[
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="doctor_notification_preferences",
                        serialize=False,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("new_appointment_booking", models.BooleanField(default=True)),
                ("appointment_cancellation", models.BooleanField(default=True)),
                ("appointment_confirmed", models.BooleanField(default=True)),
                ("new_walk_in_appointment", models.BooleanField(default=True)),
                ("next_visit", models.BooleanField(default=True)),
                ("payment_balance_reminder", models.BooleanField(default=True)),
                ("sms_delivery_failure", models.BooleanField(default=True)),
            ],
        ),
    ]
