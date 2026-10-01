"""A small write API that excludes request bodies and personal details by design."""

from .audit_models import AuditEvent


_TARGET_TYPES = {
    "user": "account",
    "patientprofile": "patient",
    "treatmentrecord": "treatment",
    "appointment": "appointment",
    "smsmessage": "sms",
}

# Never copy arbitrary payload or exception data into the audit table. Only
# these fixed tokens may be retained, even when callers supply other metadata.
_SAFE_METADATA_VALUES = {
    "channel": {"sms", "email"},
    "origin": {"doctor", "patient", "system"},
}


def record_audit_event(event, *, actor=None, target=None, request=None, metadata=None):
    """Record an allowed event with opaque references and no free-form PHI."""
    if event not in AuditEvent.Event.values:
        raise ValueError(f"Unsupported audit event: {event}")

    if actor is None and request is not None:
        actor = getattr(request, "user", None)
    if not getattr(actor, "is_authenticated", False):
        actor = None

    target_type = ""
    target_id = ""
    if target is not None:
        model_meta = getattr(target, "_meta", None)
        model_name = getattr(model_meta, "model_name", "")
        target_type = _TARGET_TYPES.get(model_name, "")
        if target_type:
            target_id = str(getattr(target, "pk", "") or "")[:64]

    safe_metadata = {}
    if isinstance(metadata, dict):
        for key, allowed_values in _SAFE_METADATA_VALUES.items():
            value = metadata.get(key)
            if isinstance(value, str) and value in allowed_values:
                safe_metadata[key] = value

    return AuditEvent.objects.create(
        event=event,
        actor=actor,
        actor_id_snapshot=str(actor.pk)[:64] if actor else "",
        actor_role=str(actor.role)[:16] if actor else "",
        target_type=target_type,
        target_id=target_id,
        result=(
            AuditEvent.Result.FAILED
            if event == AuditEvent.Event.LOGIN_FAILED
            else AuditEvent.Result.SUCCESS
        ),
        metadata=safe_metadata,
    )

