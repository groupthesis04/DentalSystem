from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import PatientConsentRecord, PatientProfile, User


@admin.register(User)
class ClinicUserAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "name", "role", "is_active", "is_staff")
    search_fields = ("email", "name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("name", "phone", "role", "profile_image")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined", "updated_at")}),
    )
    readonly_fields = ("updated_at",)
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "name", "role", "password1", "password2")}),
    )


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "mobile_number", "birthdate", "user")
    search_fields = ("first_name", "middle_name", "last_name", "email")
    readonly_fields = (
        "privacy_consent_given", "privacy_consent_at", "privacy_version",
        "privacy_consent_recorded_by", "sms_consent", "sms_consent_at",
        "sms_consent_method", "sms_consent_recorded_by", "sms_stop_reason",
        "sms_stop_reason_detail",
    )


@admin.register(PatientConsentRecord)
class PatientConsentRecordAdmin(admin.ModelAdmin):
    list_display = ("patient_id_snapshot", "kind", "action", "consent_given", "actor_id_snapshot", "recorded_at")
    readonly_fields = (
        "patient", "patient_id_snapshot", "kind", "action", "consent_given",
        "patient_choice_confirmed",
        "method", "purpose", "notice_version", "stop_reason", "stop_reason_detail",
        "actor", "actor_id_snapshot", "actor_role", "recorded_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
