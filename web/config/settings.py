import os
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def build_identifier() -> str:
    try:
        return subprocess.check_output(
            [
                "git", "log", "-1", "--format=%cd",
                "--date=format:%Y%m%d-%H%M",
            ],
            cwd=BASE_DIR.parent,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        build_file = BASE_DIR / ".silverlists-build-version"
        if build_file.exists():
            return build_file.read_text(encoding="utf-8").strip()
        return "development"


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "development-only-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
SILVERLISTS_BUILD = build_identifier()
SILVERLISTS_BASE_URL = os.getenv("SILVERLISTS_BASE_URL", "").strip().rstrip("/")
if SILVERLISTS_BASE_URL:
    parsed_base_url = urlsplit(SILVERLISTS_BASE_URL)
    if (parsed_base_url.scheme not in {"http", "https"} or
            not parsed_base_url.hostname or parsed_base_url.query or parsed_base_url.fragment):
        raise ImproperlyConfigured(
            "SILVERLISTS_BASE_URL muss eine vollständige HTTP(S)-URL ohne Query oder Fragment sein."
        )
    SILVERLISTS_URL_PREFIX = parsed_base_url.path.rstrip("/")
    SILVERLISTS_ORIGIN = f"{parsed_base_url.scheme}://{parsed_base_url.netloc}"
else:
    parsed_base_url = None
    SILVERLISTS_URL_PREFIX = ""
    SILVERLISTS_ORIGIN = ""

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
if parsed_base_url:
    ALLOWED_HOSTS.append(parsed_base_url.hostname)
ALLOWED_HOSTS = list(dict.fromkeys([*ALLOWED_HOSTS, "localhost", "127.0.0.1"]))
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
if SILVERLISTS_ORIGIN:
    CSRF_TRUSTED_ORIGINS = list(dict.fromkeys([
        *CSRF_TRUSTED_ORIGINS, SILVERLISTS_ORIGIN,
    ]))
FORCE_SCRIPT_NAME = SILVERLISTS_URL_PREFIX or None

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.build_info",
            ],
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.getenv("DJANGO_DATABASE_PATH", str(BASE_DIR / "db.sqlite3")),
    }
}

LANGUAGE_CODE = "de-de"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True

STATIC_URL = f"{SILVERLISTS_URL_PREFIX}/static/"
STATIC_ROOT = Path(os.getenv("DJANGO_STATIC_ROOT", str(BASE_DIR / "staticfiles")))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG else
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}
MEDIA_URL = f"{SILVERLISTS_URL_PREFIX}/media/"
MEDIA_ROOT = Path(os.getenv("DJANGO_MEDIA_ROOT", str(BASE_DIR / "var" / "media")))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Berichtsvorschauen werden innerhalb der eigenen Auftragsseite in einem iframe
# angezeigt. Einbettung durch fremde Origins bleibt weiterhin untersagt.
X_FRAME_OPTIONS = "SAMEORIGIN"

# Berichtskatalog im Repository; später optional durch Admin-Versionierung
# ergänzbar. DuckDB ist ausdrücklich nicht Djangos Systemdatenbank.
REPORT_DEFINITION_DIR = BASE_DIR / "report_definitions"
REPORT_ASSET_DIR = Path(os.getenv(
    "SILVERLISTS_ASSET_DIR", str(BASE_DIR / "assets")
))
_weekly_offer_images = os.getenv("SILVERLISTS_PRODUCT_IMAGE_DIR", "").strip()
WEEKLY_OFFER_IMAGE_DIR = Path(_weekly_offer_images) if _weekly_offer_images else None
WEEKLY_OFFER_IMAGE_MAX_PIXELS = int(os.getenv("SILVERLISTS_PRODUCT_IMAGE_MAX_PIXELS", "480"))
WEEKLY_OFFER_IMAGE_JPEG_QUALITY = int(os.getenv("SILVERLISTS_PRODUCT_IMAGE_JPEG_QUALITY", "82"))
MAX_UPLOAD_SIZE = int(os.getenv("SILVERLISTS_MAX_UPLOAD_MB", "100")) * 1024 * 1024

HTTPS_BASE_URL = bool(parsed_base_url and parsed_base_url.scheme == "https")
if env_bool("DJANGO_TRUST_PROXY_HTTPS", HTTPS_BASE_URL):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT")
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", HTTPS_BASE_URL)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", HTTPS_BASE_URL)
SESSION_COOKIE_PATH = f"{SILVERLISTS_URL_PREFIX}/" if SILVERLISTS_URL_PREFIX else "/"
CSRF_COOKIE_PATH = SESSION_COOKIE_PATH
