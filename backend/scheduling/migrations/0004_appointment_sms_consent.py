from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("scheduling", "0003_appointment_services")]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="appointment_sms_consent",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="appointment",
            name="appointment_sms_consent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
