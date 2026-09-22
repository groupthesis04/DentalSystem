import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def load_environment_file(path):
    """Load the small local .env file without adding another dependency."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_environment_file(BASE_DIR / ".env")

SECRET_KEY = os.environ.get(
    "DRMS_DJANGO_SECRET_KEY",
    "development-only-change-this-key-before-deployment",
)
DEBUG = os.environ.get("DRMS_DEBUG", "1") == "1"

configured_hosts = os.environ.get("DRMS_ALLOWED_HOSTS", "").strip()
if configured_hosts:
    ALLOWED_HOSTS = [host.strip() for host in configured_hosts.split(",") if host.strip()]
elif DEBUG:
    # The development server can also be opened from a phone on the same Wi-Fi.
    ALLOWED_HOSTS = ["*"]
else:
    ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "scheduling",
    "records",
    "clinic",
    "communications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "dental_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "dental_backend.wsgi.application"
ASGI_APPLICATION = "dental_backend.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("DRMS_DB_NAME", "dental_clinic"),
        "USER": os.environ.get("DRMS_DB_USER", "root"),
        "PASSWORD": os.environ.get("DRMS_DB_PASSWORD", ""),
        "HOST": os.environ.get("DRMS_DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DRMS_DB_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# Automated tests use a disposable in-memory database. Normal runs always use MySQL.
if os.environ.get("DRMS_TEST_SQLITE", "0") == "1":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_NAME = "drms_session"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_SECURE = os.environ.get("DRMS_COOKIE_SECURE", "0") == "1"
SESSION_COOKIE_AGE = 12 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = True

CSRF_COOKIE_NAME = "drms_csrf"
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
CSRF_HEADER_NAME = "HTTP_X_CSRFTOKEN"
CSRF_FAILURE_VIEW = "dental_backend.views.csrf_failure"

trusted_origins = os.environ.get("DRMS_CSRF_TRUSTED_ORIGINS", "").strip()
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in trusted_origins.split(",") if origin.strip()
]

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

DATA_UPLOAD_MAX_MEMORY_SIZE = 3_000_000
LOGIN_URL = "/api/login"

# Real SMS delivery is opt-in and credentials remain server-side.
SMS_ENABLED = os.environ.get("SMS_ENABLED", "0") == "1"
SMS_CLINIC_NAME = os.environ.get("SMS_CLINIC_NAME", "BORJA Dental Clinic")
SEMAPHORE_API_KEY = os.environ.get("SEMAPHORE_API_KEY", "").strip()
SEMAPHORE_SENDER_NAME = os.environ.get("SEMAPHORE_SENDER_NAME", "").strip()
# Semaphore permits two account lookups per minute. Keep the dashboard below that limit.
SEMAPHORE_ACCOUNT_CACHE_SECONDS = 60
