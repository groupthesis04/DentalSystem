"""Session protected dashboard invalidations; REST remains the data source."""

import logging
from types import SimpleNamespace

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.layers import get_channel_layer
from django.contrib.auth import get_user
from django.contrib.sessions.backends.db import SessionStore
from django.db import transaction


logger = logging.getLogger(__name__)
ADMIN_GROUP = "doctor-dashboard"
CHANGE_EVENT = {"type": "dashboard.changed"}


def publish_dashboard_change():
    """Notify connected clinic dashboards without carrying patient information."""
    try:
        layer = get_channel_layer()
        async_to_sync(layer.group_send)(ADMIN_GROUP, CHANGE_EVENT)
    except Exception:
        # The appointment/patient write has already committed. A disconnected
        # dashboard catches up by loading the database when it reconnects.
        logger.exception("Could not publish dashboard change")


def schedule_dashboard_change():
    transaction.on_commit(publish_dashboard_change)


@database_sync_to_async
def session_still_authorized(session_key, user_id):
    # Re-read the database session to catch logout, expiry, password changes,
    # role changes, and disabled accounts while the socket remains open.
    user = get_user(SimpleNamespace(session=SessionStore(session_key=session_key)))
    return bool(
        user.is_authenticated
        and str(user.pk) == user_id
        and user.is_active
        and user.role == "doctor"
    )


class AdminUpdatesConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.joined = False
        user = self.scope.get("user")
        session = self.scope.get("session")
        self.session_key = session.session_key if session else None
        self.user_id = str(user.pk) if user and user.is_authenticated else None
        if not (
            user
            and user.is_authenticated
            and user.is_active
            and user.role == "doctor"
            and self.session_key
        ):
            await self.close(code=4403)
            return
        await self.channel_layer.group_add(ADMIN_GROUP, self.channel_name)
        self.joined = True
        await self.accept()

    async def disconnect(self, close_code):
        if getattr(self, "joined", False):
            await self.channel_layer.group_discard(ADMIN_GROUP, self.channel_name)

    async def dashboard_changed(self, event):
        if not await session_still_authorized(self.session_key, self.user_id):
            await self.close(code=4403)
            return
        await self.send_json(CHANGE_EVENT)
