from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("communications", "0004_doctornotificationpreference"),
    ]

    operations = [
        migrations.AddField(
            model_name="doctornotificationpreference",
            name="upcoming_appointment_reminder",
            field=models.BooleanField(default=True),
        ),
    ]
