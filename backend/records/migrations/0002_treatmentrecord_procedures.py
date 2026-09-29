from django.db import migrations, models


def copy_legacy_procedures(apps, schema_editor):
    TreatmentRecord = apps.get_model("records", "TreatmentRecord")
    for record in TreatmentRecord.objects.exclude(procedure="").iterator():
        TreatmentRecord.objects.filter(pk=record.pk).update(procedures=[record.procedure])


class Migration(migrations.Migration):
    dependencies = [("records", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="treatmentrecord",
            name="procedures",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(copy_legacy_procedures, migrations.RunPython.noop),
    ]
