from django.urls import path

from . import views


urlpatterns = [
    path("services", views.services, name="services"),
    path("promos", views.promos, name="promos"),
    path("feedback", views.feedback, name="feedback"),
]
