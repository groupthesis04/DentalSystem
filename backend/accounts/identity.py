"""Conservative identity checks for patient records created without an account."""

import re

from django.db.models import Q

from .models import PatientProfile


class PatientIdentityConflict(ValueError):
    """An existing profile needs staff review before another is created."""


def normalize_ph_mobile_number(value):
    """Return a Philippine mobile number as +639XXXXXXXXX.

    Historic clinic numbers may have ordinary display separators. The accepted
    number itself must still be a ten-digit 9... mobile, with or without the
    local 0 or country code prefix.
    """
    number = re.sub(r"[\s().-]", "", str(value or "").strip())
    if re.fullmatch(r"9[0-9]{9}", number):
        return "+63" + number
    if re.fullmatch(r"09[0-9]{9}", number):
        return "+63" + number[1:]
    if re.fullmatch(r"(?:\+63|63)9[0-9]{9}", number):
        return "+" + number.lstrip("+")
    raise ValueError("Enter a valid Philippine mobile number.")


def canonical_mobile(value):
    """Keep the existing 639... comparison format for legacy callers."""
    try:
        return normalize_ph_mobile_number(value)[1:]
    except ValueError:
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
