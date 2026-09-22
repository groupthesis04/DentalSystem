from django.contrib import admin
from django.urls import include, path

from . import views


urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/", include("scheduling.urls")),
    path("api/", include("records.urls")),
    path("api/", include("clinic.urls")),
    path("api/", include("communications.urls")),
    path("api/reports", views.reports, name="reports"),
    path("api/health", views.health, name="health"),
]
