from django.contrib import admin

from .models import Appointment, AvailabilitySlot


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("patient_name", "service_name", "appointment_date", "appointment_time", "status")
    list_filter = ("status", "appointment_date", "source")
    search_fields = ("patient_name", "patient_email", "service_name")


@admin.register(AvailabilitySlot)
class AvailabilitySlotAdmin(admin.ModelAdmin):
    list_display = ("doctor_name", "date", "time")
    list_filter = ("date",)
