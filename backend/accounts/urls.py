from django.urls import path

from . import audit_views, password_reset, security_views, views


urlpatterns = [
    path("session", views.session, name="session"),
    path("register", views.register, name="register"),
    path("email-validation", views.email_validation, name="email_validation"),
    path("account-verification/verify", views.verify_account, name="verify_account"),
    path("account-verification/resend", views.resend_account_code, name="resend_account_code"),
    path("login", views.login, name="login"),
    path("logout", views.logout, name="logout"),
    path("password-reset/request", password_reset.request_password_reset, name="password_reset_request"),
    path("password-reset/verify", password_reset.verify_password_reset, name="password_reset_verify"),
    path("password-reset/resend", password_reset.resend_password_reset, name="password_reset_resend"),
    path("password-reset/confirm", password_reset.confirm_password_reset, name="password_reset_confirm"),
    path("profile", views.profile, name="profile"),
    path("account/security", security_views.security, name="account_security"),
    path("account/activity-log", audit_views.activity_log, name="account_activity_log"),
    path("account/change-password", security_views.change_password, name="account_change_password"),
    path("account/recovery-contact", security_views.recovery_contact, name="account_recovery_contact"),
    path("account/logout-other-devices", security_views.logout_other_devices, name="account_logout_other_devices"),
    path("account/sms-preference", views.sms_preference, name="account_sms_preference"),
    path("patients", views.patients, name="patients"),
]
