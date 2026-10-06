import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import OriginValidator
from django.conf import settings
from django.core.asgi import get_asgi_application
from django.core.exceptions import ImproperlyConfigured
from django.urls import path


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dental_backend.settings")
django_asgi_app = get_asgi_application()
if (
    not settings.DEBUG
    and os.environ.get("DRMS_TEST_SQLITE", "0") != "1"
    and not os.environ.get("REDIS_URL", "").strip()
):
    raise ImproperlyConfigured("Set REDIS_URL for production dashboard updates.")

from dental_backend.realtime import AdminUpdatesConsumer  # noqa: E402

allowed_origins = list(settings.CSRF_TRUSTED_ORIGINS)
if settings.DEBUG:
    allowed_origins += [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": OriginValidator(
        AuthMiddlewareStack(URLRouter([
            path("ws/admin-updates/", AdminUpdatesConsumer.as_asgi()),
        ])),
        allowed_origins,
    ),
})
