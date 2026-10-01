from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_account_lockout"),
    ]

    operations = [
        migrations.AddField(
            model_name="patientprofile",
            name="privacy_consent_given",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="patientprofile",
            name="privacy_consent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="patientprofile",
            name="privacy_version",
            field=models.CharField(blank=True, max_length=40),
        ),
        # Existing patients retain their existing reminder behavior and show
        # "not recorded" until they make a choice. New profiles default false.
        migrations.AddField(
            model_name="patientprofile",
            name="sms_consent",
            field=models.BooleanField(null=True),
        ),
        migrations.AlterField(
            model_name="patientprofile",
            name="sms_consent",
            field=models.BooleanField(default=False, null=True),
        ),
        migrations.AddField(
            model_name="patientprofile",
            name="sms_consent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="patientaccountverification",
            name="privacy_version",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="patientaccountverification",
            name="sms_consent",
            field=models.BooleanField(default=False),
        ),
    ]
