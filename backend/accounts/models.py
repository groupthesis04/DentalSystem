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
