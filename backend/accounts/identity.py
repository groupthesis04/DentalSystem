"""Conservative identity checks for patient records created without an account."""

import re

from django.db.models import Q

from .models import PatientProfile


class PatientIdentityConflict(ValueError):
    """An existing profile needs staff review before another is created."""


def canonical_mobile(value):
    """Return the same value for 09..., 639..., and +639... mobile numbers."""
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 11 and digits.startswith("09"):
        return "63" + digits[1:]
    if len(digits) == 12 and digits.startswith("639"):
        return digits
    return ""


def normalized_full_name(first_name, middle_name="", last_name=""):
    return " ".join(" ".join(part for part in (first_name, middle_name, last_name) if part).casefold().split())


def profile_has_mobile(profile, mobile):
    return bool(mobile) and any(
        canonical_mobile(value) == mobile
        for value in (profile.mobile_number, profile.phone_number)
    )


def identity_candidates(email, birthdate, full_name, *, for_update=False, exclude_id=None):
    """Fetch possible matches; phone comparisons happen after PH format normalization."""
    filters = Q()
    if email:
        filters |= Q(email__iexact=email)
    if birthdate:
        filters |= Q(birthdate=birthdate)
        # A clinic record without a birthdate cannot be ruled out by date.
        filters |= Q(birthdate__isnull=True)
    if full_name:
        filters |= Q(normalized_name=full_name)
    queryset = PatientProfile.objects.filter(filters).order_by("id")
    if exclude_id:
        queryset = queryset.exclude(id=exclude_id)
    if for_update:
        queryset = queryset.select_for_update()
    return list(queryset)


def creation_conflict(email, phone, birthdate, full_name, exclude_id=None):
    """Find a likely existing record before staff creates another profile."""
    mobile = canonical_mobile(phone)
    if mobile and not birthdate:
        # Without a birthdate, staff cannot distinguish patients who share a
        # mobile number. Ask them to select a record or collect the date.
        queryset = PatientProfile.objects.all().order_by("id")
        if exclude_id:
            queryset = queryset.exclude(id=exclude_id)
        for profile in queryset:
            if profile_has_mobile(profile, mobile):
                return profile
    for profile in identity_candidates(email, birthdate, full_name, exclude_id=exclude_id):
        same_email = bool(email and profile.email and profile.email.casefold() == email.casefold())
        same_name = bool(full_name and profile.normalized_name == full_name)
        same_birthdate = bool(birthdate and profile.birthdate == birthdate)
        same_phone = profile_has_mobile(profile, mobile)
        if same_email or (same_birthdate and (same_name or same_phone)):
            return profile
        if same_phone and not profile.birthdate:
            return profile
    return None
