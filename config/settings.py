"""Configuración del sistema Definitively Bolivia (Django 5 + PostgreSQL 16)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _cargar_env():
    """Lee el archivo .env (clave=valor) sin depender de librerías externas."""
    ruta = BASE_DIR / ".env"
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_cargar_env()

SECRET_KEY = os.environ.get("SECRET_KEY", "definitively-bolivia-clave-local-cambiar-en-produccion")
DEBUG = os.environ.get("DEBUG", "1") == "1"
ALLOWED_HOSTS = ["*"] if DEBUG else ["localhost", "127.0.0.1"]

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "django.contrib.messages",
    "agencia",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "agencia.middleware.UsuarioMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.messages.context_processors.messages",
        "agencia.context.base",
    ]},
}]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "agencia_viajes"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "postgres"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "ATOMIC_REQUESTS": True,
        "OPTIONS": {"client_encoding": "UTF8"},
    }
}

# Sesiones firmadas en cookie: no se necesita ninguna tabla extra en la base de datos
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
SESSION_COOKIE_AGE = 60 * 60 * 8
SESSION_COOKIE_HTTPONLY = True
MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.PBKDF2PasswordHasher"]

LANGUAGE_CODE = "es-bo"
TIME_ZONE = "America/La_Paz"
USE_I18N = False
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_ROOT = BASE_DIR / "media"
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
