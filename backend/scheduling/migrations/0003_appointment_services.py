from django.db import migrations, models


def copy_legacy_services(apps, schema_editor):
    Appointment = apps.get_model("scheduling", "Appointment")
    for appointment in Appointment.objects.exclude(service_name="").iterator():
        Appointment.objects.filter(pk=appointment.pk).update(services=[appointment.service_name])


class Migration(migrations.Migration):
    dependencies = [("scheduling", "0002_availabilityslot")]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="services",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(copy_legacy_services, migrations.RunPython.noop),
    ]
