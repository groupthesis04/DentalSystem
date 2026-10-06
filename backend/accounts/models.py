import secrets

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        extra_fields.setdefault("id", f"usr_{secrets.token_hex(6)}")
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("name", "System Administrator")
        extra_fields.setdefault("role", "doctor")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [("patient", "Patient"), ("doctor", "Doctor")]

    id = models.CharField(primary_key=True, max_length=64)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=24, blank=True)
    recovery_email = models.EmailField(blank=True)
    recovery_mobile_number = models.CharField(max_length=24, blank=True)
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, db_index=True)
    profile_image = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    legacy_payload = models.JSONField(default=dict, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    def __str__(self):
        return f"{self.name} ({self.email})"


class PatientProfile(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="patient_profile",
        null=True,
        blank=True,
    )
    first_name = models.CharField(max_length=80)
    middle_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80)
    normalized_name = models.CharField(max_length=220, db_index=True)
    email = models.EmailField(blank=True, db_index=True)
    birthdate = models.DateField(null=True, blank=True)
    age = models.PositiveSmallIntegerField(null=True, blank=True)
    sex = models.CharField(max_length=24, blank=True)
    address = models.CharField(max_length=300, blank=True)
    nationality = models.CharField(max_length=80, blank=True)
    occupation = models.CharField(max_length=120, blank=True)
    phone_number = models.CharField(max_length=24, blank=True)
    mobile_number = models.CharField(max_length=24, blank=True)
    notes = models.TextField(blank=True)
    privacy_consent_given = models.BooleanField(default=False)
    privacy_consent_at = models.DateTimeField(null=True, blank=True)
    privacy_version = models.CharField(max_length=40, blank=True)
    privacy_consent_recorded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="privacy_consent_recordings",
    )
    # NULL marks pre-consent records whose historic choice was not recorded.
    # Newly created profiles default to False until the patient opts in.
    sms_consent = models.BooleanField(default=False, null=True)
    sms_consent_at = models.DateTimeField(null=True, blank=True)
    sms_consent_method = models.CharField(max_length=16, blank=True)
    sms_consent_recorded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="sms_consent_recordings",
    )
    sms_stop_reason = models.CharField(max_length=32, blank=True)
    sms_stop_reason_detail = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    legacy_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["normalized_name", "birthdate"],
                name="patient_identity_uniq",
            )
        ]
        indexes = [models.Index(fields=["email"], name="patient_email_idx")]

    @property
    def name(self):
        return " ".join(
            part for part in (self.first_name, self.middle_name, self.last_name) if part
        )

    @property
    def phone(self):
        return self.mobile_number or self.phone_number

    def save(self, *args, **kwargs):
        self.normalized_name = " ".join(self.name.casefold().split())
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class PatientConsentRecord(models.Model):
    """Append-only evidence of a patient choice or an operational SMS stop."""

    class Kind(models.TextChoices):
        PRIVACY = "privacy", "Privacy agreement"
        SMS = "sms", "SMS messages"

    class Action(models.TextChoices):
        RECORDED = "recorded", "Patient choice recorded"
        STOPPED = "stopped", "SMS stopped"

    patient = models.ForeignKey(
        PatientProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="consent_records",
    )
    patient_id_snapshot = models.CharField(max_length=64, db_index=True)
    kind = models.CharField(max_length=8, choices=Kind.choices)
    action = models.CharField(max_length=8, choices=Action.choices)
    # A stop can be operational (for example, a wrong number), so it does not
    # assert a new patient choice. NULL distinguishes that from a decline.
    consent_given = models.BooleanField(null=True)
    patient_choice_confirmed = models.BooleanField(default=False)
    method = models.CharField(max_length=16, blank=True)
    purpose = models.CharField(max_length=200, blank=True)
    notice_version = models.CharField(max_length=40, blank=True)
    stop_reason = models.CharField(max_length=32, blank=True)
    stop_reason_detail = models.CharField(max_length=300, blank=True)
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="patient_consent_records",
    )
    actor_id_snapshot = models.CharField(max_length=64, blank=True)
    actor_role = models.CharField(max_length=16, blank=True)
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-recorded_at", "-id"]
        indexes = [models.Index(fields=["patient", "-recorded_at"], name="consent_patient_date_idx")]


class PatientAccountVerification(models.Model):
    """A short-lived, single-use claim of a clinic-created patient record."""

    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name="account_verifications")
    token_hash = models.CharField(max_length=64, unique=True)
    phone_number = models.CharField(max_length=24)
    code_hash = models.CharField(max_length=128, blank=True)
    email = models.EmailField()
    first_name = models.CharField(max_length=80)
    middle_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80)
    birthdate = models.DateField()
    password_hash = models.CharField(max_length=128, blank=True)
    profile_image = models.TextField(blank=True)
    remember = models.BooleanField(default=False)
    privacy_version = models.CharField(max_length=40, blank=True)
    sms_consent = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["patient", "created_at"], name="patient_otp_created_idx"),
            models.Index(fields=["created_at"], name="patient_otp_old_idx"),
        ]


class PasswordResetVerification(models.Model):
    """Short-lived email OTP challenge for an existing account.

    A null user represents an indistinguishable decoy for an unknown or inactive
    email. It can never verify an OTP or change an account password.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="password_reset_verifications",
        null=True, blank=True,
    )
    email_key = models.CharField(max_length=64, db_index=True)
    masked_email = models.CharField(max_length=254)
    token_hash = models.CharField(max_length=64, unique=True)
    code_hash = models.CharField(max_length=256, blank=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    is_verified = models.BooleanField(default=False)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    verified_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["email_key", "-created_at"], name="reset_email_created_idx"),
            models.Index(fields=["user", "-created_at"], name="reset_user_created_idx"),
            models.Index(fields=["created_at"], name="reset_created_idx"),
        ]


class AccountLoginActivity(models.Model):
    """A durable record of successful account sign-ins."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_activity")
    user_agent = models.CharField(max_length=255, blank=True)
    session_key_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "-created_at"], name="account_login_user_idx")]


class AccountAuthState(models.Model):
    """Persistent failed sign-in counter shared across devices and workers."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="auth_state")
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_failed_at = models.DateTimeField(null=True, blank=True)


# Django discovers models imported from this module during app initialization.
from .audit_models import AuditEvent  # noqa: E402,F401
