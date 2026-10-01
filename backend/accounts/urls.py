from django.urls import path

from . import audit_views, security_views, views


urlpatterns = [
    path("session", views.session, name="session"),
    path("register", views.register, name="register"),
    path("account-verification/verify", views.verify_account, name="verify_account"),
    path("account-verification/resend", views.resend_account_code, name="resend_account_code"),
    path("login", views.login, name="login"),
    path("logout", views.logout, name="logout"),
    path("profile", views.profile, name="profile"),
    path("account/security", security_views.security, name="account_security"),
    path("account/activity-log", audit_views.activity_log, name="account_activity_log"),
    path("account/change-password", security_views.change_password, name="account_change_password"),
    path("account/recovery-contact", security_views.recovery_contact, name="account_recovery_contact"),
    path("account/logout-other-devices", security_views.logout_other_devices, name="account_logout_other_devices"),
    path("account/sms-preference", views.sms_preference, name="account_sms_preference"),
    path("patients", views.patients, name="patients"),
]
