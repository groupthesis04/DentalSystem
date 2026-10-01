from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from . import views


urlpatterns = [
    path("api/", include("accounts.urls")),
    path("api/", include("scheduling.urls")),
    path("api/", include("records.urls")),
    path("api/", include("clinic.urls")),
    path("api/", include("communications.urls")),
    path("api/reports", views.reports, name="reports"),
    path("api/health", views.health, name="health"),
]

# Keep the optional Django Admin entry point available only in local development.
if settings.DEBUG:
    urlpatterns.insert(0, path("django-admin/", admin.site.urls))
