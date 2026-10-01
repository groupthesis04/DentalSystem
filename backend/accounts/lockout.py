"""Persistent account sign-in lockout shared across devices and workers."""

import datetime as dt

from django.db import transaction
from django.utils import timezone

from .models import AccountAuthState


LOCK_AFTER_ATTEMPTS = 5
LOCK_DURATION = dt.timedelta(minutes=15)
FAILURE_WINDOW = dt.timedelta(minutes=15)


def account_lock_seconds(user):
    state = AccountAuthState.objects.filter(user=user).only("locked_until").first()
    if not state or not state.locked_until:
        return 0
    return max(0, int((state.locked_until - timezone.now()).total_seconds()) + 1)


def register_failed_attempt(user):
    """Return (retry_after, newly_locked) for a bad password."""
    now = timezone.now()
    with transaction.atomic():
        state, _ = AccountAuthState.objects.select_for_update().get_or_create(user=user)
        if state.locked_until and state.locked_until > now:
            return max(1, int((state.locked_until - now).total_seconds()) + 1), False
        if state.last_failed_at is None or state.last_failed_at < now - FAILURE_WINDOW:
            state.failed_attempts = 0
        state.failed_attempts += 1
        state.last_failed_at = now
        state.locked_until = now + LOCK_DURATION if state.failed_attempts >= LOCK_AFTER_ATTEMPTS else None
        state.save(update_fields=["failed_attempts", "last_failed_at", "locked_until"])
        return (int(LOCK_DURATION.total_seconds()), True) if state.locked_until else (0, False)


def clear_failed_attempts(user):
    AccountAuthState.objects.filter(user=user).update(
        failed_attempts=0, last_failed_at=None, locked_until=None
    )
