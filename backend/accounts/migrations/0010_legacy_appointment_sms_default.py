"""Let old MySQL patient tables accept new accounts without changing consent data."""

from django.db import migrations


def repair_legacy_column(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "mysql":
        return

    table_name = apps.get_model("accounts", "PatientProfile")._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT IS_NULLABLE, COLUMN_DEFAULT, COLUMN_TYPE
               FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
                 AND COLUMN_NAME = %s""",
            [table_name, "appointment_sms_consent"],
        )
        column = cursor.fetchone()

    # Some older installations kept this column after the application stopped
    # using it. Its missing default makes every new patient insert fail.
    if column != ("NO", None, "tinyint(1)"):
        return

    table = schema_editor.quote_name(table_name)
    field = schema_editor.quote_name("appointment_sms_consent")
    schema_editor.execute(
        f"ALTER TABLE {table} MODIFY COLUMN {field} TINYINT(1) NOT NULL DEFAULT 0"
    )


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("accounts", "0009_password_reset_verification")]

    operations = [
        migrations.RunPython(repair_legacy_column, migrations.RunPython.noop, atomic=False)
    ]
