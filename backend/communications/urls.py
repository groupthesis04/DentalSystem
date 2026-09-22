from django.urls import path

from . import sms_views, views


urlpatterns = [
    path("notifications", views.notifications, name="notifications"),
    path("messages", views.messages, name="messages"),
    path("sms", sms_views.dashboard, name="sms-dashboard"),
    path("sms/rules", sms_views.rules, name="sms-rules"),
    path("sms/templates", sms_views.templates, name="sms-templates"),
    path("sms/logs", sms_views.logs, name="sms-logs"),
    path("sms/resend", sms_views.resend, name="sms-resend"),
    path("sms/test", sms_views.test_sms, name="sms-test"),
]
