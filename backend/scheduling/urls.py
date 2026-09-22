from django.urls import path

from . import views


urlpatterns = [
    path("appointments", views.appointments, name="appointments"),
    path("availability", views.availability, name="availability"),
]
