import datetime as dt
import json
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone

from accounts.models import PatientProfile, User
from clinic.models import Feedback, Promotion, Service
from communications.models import Message, Notification
from dental_backend.api import calculate_age, split_name
from records.models import TreatmentRecord
from scheduling.models import Appointment, AvailabilitySlot


def safe_text(value):
    return str(value or "").strip()


def safe_date(value):
    if isinstance(value, dt.date):
        return value
    text = safe_text(value)[:10]
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        return None


def safe_time(value):
    if isinstance(value, dt.time):
        return value.replace(tzinfo=None)
    text = safe_text(value)[:8]
    if not text:
        return None
    try:
        return dt.time.fromisoformat(text)
    except ValueError:
        return None


def safe_datetime(value):
    if not value:
        return None
    if isinstance(value, dt.datetime):
        result = value
    else:
        text = safe_text(value).replace("Z", "+00:00")
        try:
            result = dt.datetime.fromisoformat(text)
        except ValueError:
            return None
    if timezone.is_naive(result):
        result = timezone.make_aware(result, timezone.get_current_timezone())
    return result


def json_safe(row):
    converted = {}
    for key, value in row.items():
        if isinstance(value, (dt.date, dt.time, dt.datetime, Decimal)):
            converted[key] = str(value)
        elif isinstance(value, bytes):
            converted[key] = value.decode("utf-8", errors="replace")
        else:
            converted[key] = value
    return converted


def money(value):
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


class Command(BaseCommand):
    help = "Copy rows from the legacy mysql-connector tables into Django ORM tables."

    def table_rows(self, table_name):
        existing = set(connection.introspection.table_names())
        if table_name not in existing:
            return []
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT * FROM `{table_name}`")
            columns = [column[0] for column in cursor.description]
            rows = []
            for raw_row in cursor.fetchall():
                database_row = dict(zip(columns, raw_row))
                payload = database_row.get("payload")
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except json.JSONDecodeError:
                        payload = {}
                if not isinstance(payload, dict):
                    payload = {}
                rows.append({**payload, **database_row})
            return rows

    def ensure_patient_profile(self, user):
        profile = PatientProfile.objects.filter(user=user).first()
        if profile:
            return profile
        first_name, middle_name, last_name = split_name(user.name)
        profile, _ = PatientProfile.objects.get_or_create(
            id=user.id,
            defaults={
                "user": user,
                "first_name": first_name,
                "middle_name": middle_name,
                "last_name": last_name,
                "email": user.email,
                "phone_number": user.phone,
                "mobile_number": user.phone,
                "legacy_payload": user.legacy_payload,
            },
        )
        if profile.user_id is None:
            profile.user = user
            profile.save(update_fields=["user", "updated_at"])
        return profile

    def restore_created_at(self, model, object_id, row):
        """Preserve legacy ordering without overwriting later application edits."""
        created_at = safe_datetime(row.get("created_at"))
        if created_at:
            model.objects.filter(pk=object_id).update(created_at=created_at)

    def resolve_patient(self, patient_id):
        profile = PatientProfile.objects.filter(id=patient_id).first()
        if profile:
            return profile
        user = User.objects.filter(id=patient_id, role="patient").first()
        return self.ensure_patient_profile(user) if user else None

    def handle(self, *args, **options):
        counts = {}
        with transaction.atomic():
            counts["users"] = self.import_users()
            counts["patients"] = self.import_patients()
            counts["services"] = self.import_services()
            counts["promos"] = self.import_promos()
            counts["feedback"] = self.import_feedback()
            counts["availability"] = self.import_availability()
            counts["appointments"] = self.import_appointments()
            counts["treatments"] = self.import_treatments()
            counts["notifications"] = self.import_notifications()
            counts["messages"] = self.import_messages()
        summary = ", ".join(f"{name}: {count} added" for name, count in counts.items())
        self.stdout.write(self.style.SUCCESS(f"Legacy import complete ({summary})."))

    def import_users(self):
        added = 0
        for row in self.table_rows("users"):
            user_id = safe_text(row.get("id"))
            if not user_id:
                continue
            defaults = {
                "email": safe_text(row.get("email")).lower(),
                "name": safe_text(row.get("name")) or "Patient",
                "phone": safe_text(row.get("phone"))[:24],
                "role": safe_text(row.get("role")).lower() or "patient",
                "profile_image": safe_text(row.get("profile_image")),
                "password": safe_text(row.get("password_hash")),
                "is_active": True,
                "is_staff": safe_text(row.get("role")).lower() == "doctor",
                "date_joined": safe_datetime(row.get("created_at")) or timezone.now(),
                "legacy_payload": json_safe(row),
            }
            user, created = User.objects.get_or_create(id=user_id, defaults=defaults)
            if created:
                added += 1
            elif not user.legacy_payload:
                User.objects.filter(id=user.id).update(legacy_payload=json_safe(row))
        for user in User.objects.filter(role="patient"):
            self.ensure_patient_profile(user)
        return added

    def import_patients(self):
        added = 0
        for row in self.table_rows("patient_profiles"):
            patient_id = safe_text(row.get("id"))
            if not patient_id:
                continue
            full_name = safe_text(row.get("name"))
            first_name = safe_text(row.get("first_name"))
            middle_name = safe_text(row.get("middle_name"))
            last_name = safe_text(row.get("last_name"))
            if not first_name or not last_name:
                parsed_first, parsed_middle, parsed_last = split_name(full_name)
                first_name = first_name or parsed_first
                middle_name = middle_name or parsed_middle
                last_name = last_name or parsed_last
            birthdate = safe_date(row.get("birthdate"))
            user = User.objects.filter(id=patient_id, role="patient").first()
            defaults = {
                "user": user,
                "first_name": first_name or "Patient",
                "middle_name": middle_name,
                "last_name": last_name,
                "email": safe_text(row.get("email")).lower(),
                "birthdate": birthdate,
                "age": int(row.get("age")) if str(row.get("age") or "").isdigit() else calculate_age(birthdate),
                "sex": safe_text(row.get("sex"))[:24],
                "address": safe_text(row.get("address"))[:300],
                "nationality": safe_text(row.get("nationality"))[:80],
                "occupation": safe_text(row.get("occupation"))[:120],
                "phone_number": safe_text(row.get("phone_number") or row.get("phone"))[:24],
                "mobile_number": safe_text(row.get("mobile_number") or row.get("phone"))[:24],
                "notes": safe_text(row.get("notes")),
                "legacy_payload": json_safe(row),
            }
            profile, created = PatientProfile.objects.get_or_create(id=patient_id, defaults=defaults)
            if created:
                added += 1
            elif user and not profile.user_id:
                profile.user = user
                profile.save(update_fields=["user", "updated_at"])
        return added

    def import_services(self):
        added = 0
        for row in self.table_rows("services"):
            item, created = Service.objects.get_or_create(
                id=safe_text(row.get("id")),
                defaults={
                    "name": safe_text(row.get("name"))[:120],
                    "description": safe_text(row.get("description"))[:500],
                    "detail_tagline": safe_text(row.get("detail_tagline"))[:240],
                    "detail_items": safe_text(row.get("detail_items")),
                    "detail_duration": safe_text(row.get("detail_duration"))[:80],
                    "detail_audience": safe_text(row.get("detail_audience"))[:80],
                    "detail_care_note": safe_text(row.get("detail_care_note"))[:100],
                    "legacy_payload": json_safe(row),
                },
            )
            added += int(created)
            self.restore_created_at(Service, item.id, row)
        return added

    def import_promos(self):
        added = 0
        for row in self.table_rows("promos"):
            item, created = Promotion.objects.get_or_create(
                id=safe_text(row.get("id")),
                defaults={
                    "title": safe_text(row.get("title"))[:120],
                    "description": safe_text(row.get("description"))[:500],
                    "legacy_payload": json_safe(row),
                },
            )
            added += int(created)
            self.restore_created_at(Promotion, item.id, row)
        return added

    def import_feedback(self):
        added = 0
        for row in self.table_rows("feedback"):
            item, created = Feedback.objects.get_or_create(
                id=safe_text(row.get("id")),
                defaults={
                    "name": safe_text(row.get("name"))[:80] or "Clinic Visitor",
                    "rating": int(row.get("rating") or 5),
                    "message": safe_text(row.get("message"))[:500],
                    "updated_by": User.objects.filter(id=safe_text(row.get("updated_by"))).first(),
                    "legacy_payload": json_safe(row),
                },
            )
            added += int(created)
            self.restore_created_at(Feedback, item.id, row)
        return added

    def import_availability(self):
        added = 0
        for row in self.table_rows("availability"):
            date_value = safe_date(row.get("date") or row.get("availability_date"))
            time_value = safe_time(row.get("time") or row.get("availability_time"))
            if not date_value or not time_value:
                continue
            doctor_name = safe_text(row.get("doctor") or row.get("doctor_name"))
            doctor = User.objects.filter(role="doctor", name__iexact=doctor_name).first()
            item, created = AvailabilitySlot.objects.get_or_create(
                id=safe_text(row.get("id")),
                defaults={
                    "doctor": doctor,
                    "doctor_name": doctor_name,
                    "date": date_value,
                    "time": time_value,
                    "legacy_payload": json_safe(row),
                },
            )
            added += int(created)
            self.restore_created_at(AvailabilitySlot, item.id, row)
        return added

    def import_appointments(self):
        added = 0
        for row in self.table_rows("appointments"):
            appointment_id = safe_text(row.get("id"))
            patient = self.resolve_patient(safe_text(row.get("patient_id")))
            date_value = safe_date(row.get("date") or row.get("appointment_date"))
            time_value = safe_time(row.get("time") or row.get("appointment_time"))
            if not appointment_id or not patient or not date_value or not time_value:
                continue
            doctor_name = safe_text(row.get("doctor") or row.get("doctor_name"))
            doctor = User.objects.filter(role="doctor", name__iexact=doctor_name).first()
            created_by = User.objects.filter(id=safe_text(row.get("created_by"))).first()
            manual = bool(row.get("manual_booking"))
            source = "manual" if manual else "patient"
            if manual and safe_text(row.get("notes")).lower().startswith("follow-up"):
                source = "follow_up"
            item, created = Appointment.objects.get_or_create(
                id=appointment_id,
                defaults={
                    "patient": patient,
                    "doctor": doctor,
                    "created_by": created_by,
                    "patient_name": safe_text(row.get("patient_name")) or patient.name,
                    "patient_email": safe_text(row.get("patient_email")),
                    "patient_phone": safe_text(row.get("patient_phone"))[:24],
                    "doctor_name": doctor_name,
                    "service_name": safe_text(row.get("service"))[:120],
                    "appointment_date": date_value,
                    "appointment_time": time_value,
                    "status": safe_text(row.get("status")).lower() or "pending",
                    "source": source,
                    "notes": safe_text(row.get("notes")),
                    "booking_token": safe_text(row.get("booking_token")) or None,
                    "legacy_payload": json_safe(row),
                },
            )
            added += int(created)
            self.restore_created_at(Appointment, item.id, row)
        return added

    def import_treatments(self):
        added = 0
        for row in self.table_rows("treatments"):
            record_id = safe_text(row.get("id"))
            patient = self.resolve_patient(safe_text(row.get("patient_id")))
            treatment_date = safe_date(row.get("treatment_date")) or safe_date(row.get("created_at"))
            if not record_id or not patient or not treatment_date:
                continue
            doctor = User.objects.filter(id=safe_text(row.get("doctor_id"))).first()
            appointment = Appointment.objects.filter(id=safe_text(row.get("appointment_id"))).first()
            charged = money(row.get("amount_charged"))
            paid = money(row.get("amount_paid"))
            balance = money(row.get("balance")) if row.get("balance") is not None else charged - paid
            procedure = safe_text(row.get("procedure") or row.get("treatment") or row.get("diagnosis"))
            item, created = TreatmentRecord.objects.get_or_create(
                id=record_id,
                defaults={
                    "appointment": appointment,
                    "patient": patient,
                    "doctor": doctor,
                    "patient_name": safe_text(row.get("patient_name")) or patient.name,
                    "doctor_name": safe_text(row.get("doctor_name")) or (doctor.name if doctor else ""),
                    "treatment_date": treatment_date,
                    "tooth_numbers": safe_text(row.get("tooth_numbers"))[:120],
                    "procedure": procedure[:120],
                    "amount_charged": charged,
                    "amount_paid": paid,
                    "balance": balance,
                    "payment_status": safe_text(row.get("payment_status")) or ("completed" if balance <= 0 else "unpaid"),
                    "diagnosis": safe_text(row.get("diagnosis")),
                    "treatment": safe_text(row.get("treatment")) or procedure,
                    "prescription": safe_text(row.get("prescription")),
                    "notes": safe_text(row.get("notes")),
                    "remarks": safe_text(row.get("remarks") or row.get("notes")),
                    "next_visit": safe_date(row.get("next_visit")),
                    "legacy_payload": json_safe(row),
                },
            )
            added += int(created)
            self.restore_created_at(TreatmentRecord, item.id, row)
        return added

    def import_notifications(self):
        added = 0
        for row in self.table_rows("notifications"):
            recipient = User.objects.filter(id=safe_text(row.get("recipient_id"))).first()
            if not recipient:
                continue
            read_value = row.get("read", row.get("is_read", False))
            item, created = Notification.objects.get_or_create(
                id=safe_text(row.get("id")),
                defaults={
                    "recipient": recipient,
                    "notification_type": safe_text(row.get("type") or row.get("notification_type"))[:40],
                    "title": safe_text(row.get("title"))[:120],
                    "message": safe_text(row.get("message")),
                    "entity_type": safe_text(row.get("entity_type"))[:40],
                    "entity_id": safe_text(row.get("entity_id"))[:64],
                    "is_read": bool(read_value),
                    "read_at": safe_datetime(row.get("read_at")),
                    "legacy_payload": json_safe(row),
                },
            )
            added += int(created)
            if not item.notification_type:
                item.notification_type = safe_text(
                    row.get("type") or row.get("notification_type")
                )[:40]
                item.legacy_payload = json_safe(row)
                item.save(update_fields=["notification_type", "legacy_payload"])
            self.restore_created_at(Notification, item.id, row)
        return added

    def import_messages(self):
        added = 0
        for row in self.table_rows("messages"):
            sender = User.objects.filter(id=safe_text(row.get("sender_id"))).first()
            recipient = User.objects.filter(id=safe_text(row.get("recipient_id"))).first()
            if not sender or not recipient:
                continue
            item, created = Message.objects.get_or_create(
                id=safe_text(row.get("id")),
                defaults={
                    "sender": sender,
                    "recipient": recipient,
                    "body": safe_text(row.get("body") or row.get("message")),
                    "is_read": bool(row.get("read", row.get("is_read", False))),
                    "read_at": safe_datetime(row.get("read_at")),
                    "legacy_payload": json_safe(row),
                },
            )
            added += int(created)
            self.restore_created_at(Message, item.id, row)
        return added
