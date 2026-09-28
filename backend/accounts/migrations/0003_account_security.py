import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_patientaccountverification"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="recovery_email",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="user",
            name="recovery_mobile_number",
            field=models.CharField(blank=True, max_length=24),
        ),
        migrations.CreateModel(
            name="AccountLoginActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user_agent", models.CharField(blank=True, max_length=255)),
                ("session_key_hash", models.CharField(blank=True, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="login_activity",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [models.Index(fields=["user", "-created_at"], name="account_login_user_idx")],
            },
        ),
    ]
