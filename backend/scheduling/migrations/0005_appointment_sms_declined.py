from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("scheduling", "0004_appointment_sms_consent")]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="appointment_sms_declined",
            field=models.BooleanField(default=False),
        ),
    ]
