import dj_database_url
import os
import re

from datetime import timedelta
from dotenv import load_dotenv
from pathlib import Path

from django.contrib.messages import constants as messages

from .env_helpers import get_env_var

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Define the log directory
LOG_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = get_env_var('DJANGO_SECRET_KEY')

JWT_SIGNING_KEY = get_env_var('JWT_SIGNING_KEY')
JWT_ALG = os.environ.get('JWT_ALG', "HS256")
JWT_ACCESS_TOKEN_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "60"))
JWT_REFRESH_TOKEN_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_DAYS", "30"))

# geting from env var from now, but in the future this infos should
# come with the service registration post request
AVAILABLE_SERVICES = {
    'FarmCalendar':
    {
        'api': os.getenv('FARM_CALENDAR_API', 'http://127.0.0.1:8002/api/'),
        'post_auth': os.getenv('FARM_CALENDAR_POST_AUTH', 'http://127.0.0.1:8002/post_auth/')
    },
    'IrrigationManagement':
    {
        'api': os.getenv('IRM_API', 'http://127.0.0.1:5173/api/'),
        'post_auth': os.getenv('IRM_POST_AUTH', 'http://127.0.0.1:5173/post_auth/')
    }
}

INTERNAL_GK_URL = os.getenv('INTERNAL_GK_URL', 'http://gatekeeper:8001/')

# Default DEBUG to False
DEBUG = os.getenv('DJANGO_DEBUG', 'False') == 'True'
# DEBUG = 'DJANGO_DEBUG' in os.environ and os.getenv('DJANGO_DEBUG', '').strip().lower() in ('true', '1', 't')

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']
EXTRA_ALLOWED_HOSTS = os.environ.get('EXTRA_ALLOWED_HOSTS', '')

if EXTRA_ALLOWED_HOSTS:
    EXTRA_ALLOWED_HOSTS = [host.strip() for host in EXTRA_ALLOWED_HOSTS.split(',') if host.strip()]
    ALLOWED_HOSTS.extend(EXTRA_ALLOWED_HOSTS)

ALLOWED_HOSTS = list(dict.fromkeys(ALLOWED_HOSTS))

def generate_csrf_trusted_origins(base_domains):
    origins = []
    dev_ports = ["8001", "8002", "8003", "8004", "8005", "8006"]
    for base in base_domains:
        base = base.strip()
        if not base:
            continue

        # Normalise '.example.com' -> 'example.com'
        if base.startswith('.'):
            base = base[1:]

        if base in ("localhost", "127.0.0.1", "[::1]"):
            # Local dev: accept http/https and common ports
            origins.append(f"http://{base}")
            origins.append(f"https://{base}")
            for port in dev_ports:
                origins.append(f"http://{base}:{port}")
        else:
            # Public base: allow exact and wildcard subdomains
            origins.append(f"https://{base}")
            origins.append(f"https://*.{base}")

    # De-duplicate while keeping order
    seen = set()
    deduped = []
    for o in origins:
        if o not in seen:
            seen.add(o)
            deduped.append(o)
    return deduped


_extra_hosts_raw = os.getenv("EXTRA_ALLOWED_HOSTS", "")
_extra_hosts = [h.strip() for h in _extra_hosts_raw.split(",") if h.strip()]

BASE_DOMAINS = ["localhost", "127.0.0.1", "[::1]"]
for h in _extra_hosts:
    if h.startswith("."):
        BASE_DOMAINS.append(h.lstrip("."))  # ".example.com" -> "example.com"
    elif h.count(".") == 1 and not h.startswith("."):
        BASE_DOMAINS.append(h)  # treat bare base as a base

BASE_DOMAINS = list(dict.fromkeys(BASE_DOMAINS))

# CSRF: build once, from BASE_DOMAINS (includes wildcard for subdomains)
CSRF_TRUSTED_ORIGINS = generate_csrf_trusted_origins(BASE_DOMAINS)

# Behind Traefik at proxy: trust forwarded scheme/host for CSRF/redirects
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

# Secure cookies
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG

# Scope CORS to API paths
CORS_URLS_REGEX = r"^/api/.*$"

# CORS: allow base domain and any subdomain for each BASE_DOMAIN; plus localhost
CORS_ALLOWED_ORIGIN_REGEXES = []
for base in BASE_DOMAINS:
    d = base.lstrip(".").strip()
    if not d:
        continue

    if d in ("localhost", "127.0.0.1", "[::1]"):
        # Local dev, http/https with optional port
        CORS_ALLOWED_ORIGIN_REGEXES.extend([
            r"^http://localhost(?::\d+)?$",
            r"^http://127\.0\.0\.1(?::\d+)?$",
            r"^https://localhost(?::\d+)?$",
            r"^https://127\.0\.0\.1(?::\d+)?$",
        ])
    else:
        # Allow base and any depth of subdomains over https
        CORS_ALLOWED_ORIGIN_REGEXES.append(
            rf"^https://([a-z0-9-]+\.)*{re.escape(d)}$"
        )

# De-duplicate (preserve order)
CORS_ALLOWED_ORIGIN_REGEXES = list(dict.fromkeys(CORS_ALLOWED_ORIGIN_REGEXES))

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = ["authorization", "content-type", "x-csrftoken"]
CORS_ALLOW_METHODS = ["GET", "POST", "OPTIONS", "PUT", "PATCH", "DELETE"]

APPEND_SLASH = True

# Application definition
DEFAULT_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

LOCAL_APPS = [
    # "aegis"
    "aegis.apps.AegisConfig",       # The app that contains auth logic, configured using the app's AppConfig.
]

THIRD_PARTY_APPS = [
    "crispy_forms",
    "crispy_bootstrap4",
    'django.contrib.sites',
    'rest_framework',
    'drf_yasg',
    # 'oauth2_provider',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders'
]

INSTALLED_APPS = DEFAULT_APPS + LOCAL_APPS + THIRD_PARTY_APPS

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)


SITE_ID = 1

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap4"
CRISPY_TEMPLATE_PACK = "bootstrap4"

LOGIN_URL = "login/"
LOGIN_REDIRECT_URL = 'aegis/dashboard/'  # Redirect to the login page
LOGOUT_REDIRECT_URL = 'login'  # Redirect to the login page after logging out


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    "whitenoise.middleware.WhiteNoiseMiddleware",
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'gatekeeper.custom_middleware.ForceAppendSlashMiddleware.ForceAppendSlashMiddleware',
    # 'gatekeeper.custom_middleware.RequestLoggingMiddleware.RequestLoggingMiddleware',
]

ROOT_URLCONF = 'gatekeeper.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
            # Controls whether the template system should be in debug mode.
            "debug": True,
        },
    },
]

WSGI_APPLICATION = 'gatekeeper.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases
DATABASES = {
    'default': dj_database_url.config(
        default=(
            f'mysql://{os.getenv("DB_USER")}:{os.getenv("DB_PASS")}@'
            f'{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}'
        )
    )
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# MESSAGE_TAGS setting maps Django's built-in message levels to CSS classes used by the front-end framework
# (e.g., Bootstrap).
# This allows messages from Django's messaging framework to be styled appropriately in the web interface.
MESSAGE_TAGS = {
    messages.DEBUG: "alert-info",
    messages.INFO: "alert-info",
    messages.SUCCESS: "alert-success",
    messages.WARNING: "alert-warning",
    messages.ERROR: "alert-danger",
}


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-gb'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# WhiteNoise requires STATICFILES_STORAGE
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# STATIC_URL is the URL to use when referring to static files (like CSS, JavaScript, and images) in templates.
STATIC_URL = "/assets/"

# This setting defines the list of directories where Django will look for additional static files, in addition to
# each app's static folder.
# STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")] if DEBUG else []

# STATIC_ROOT is the directory where these static files will be collected when you run collectstatic.
STATIC_ROOT = os.path.join(BASE_DIR, 'assets')

AUTH_EXEMPT_PATHS = ["/assets/"]

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom user model replacing the default Django user model.
AUTH_USER_MODEL = 'aegis.DefaultAuthUserExtend'

DJANGO_PORT = os.getenv('DJANGO_PORT', '8001')


# same with this data, also cames in the service announcement
# in the service registration endpoint
REVERSE_PROXY_MAPPING = {
    'FarmActivities': 'FarmCalendar',
    'FarmActivityTypes': 'FarmCalendar',
    'FarmAssets': 'FarmCalendar',
    'FarmPlants': 'FarmCalendar',
    'WeeklyWeatherForecast': 'WeatherService',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=JWT_ACCESS_TOKEN_MINUTES),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=JWT_REFRESH_TOKEN_DAYS),
    'ROTATE_REFRESH_TOKENS': False,
    # 'BLACKLIST_AFTER_ROTATION': True, # Don't need this as refresh token rotation is false
    'UPDATE_LAST_LOGIN': True,

    'ALGORITHM': JWT_ALG,
    'SIGNING_KEY': JWT_SIGNING_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'JWK_URL': None,
    'LEEWAY': 0,

    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'uuid',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        # 'rest_framework_simplejwt.authentication.JWTAuthentication',
        'aegis.authentication.JWTAuthenticationWithDenylist',
        # 'oauth2_provider.contrib.rest_framework.OAuth2Authentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.AnonRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'user': '10000/day',
        'anon': '100/hour'
    }
}

# OAUTH2_PROVIDER = {
#     'ACCESS_TOKEN_EXPIRE_SECONDS': 36000,
#     'REFRESH_TOKEN_EXPIRE_SECONDS': 864000,
#
#     'SCOPES': {
#         'read': 'Read scope',
#         'write': 'Write scope',
#         'groups': 'Access to your groups',
#     }
# }

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_DIR, 'django_tests.log'),
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.db.backends': {
            'handlers': ['file', 'console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'aegis': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

FARM_CALENDAR = os.getenv('FARM_CALENDAR')
IRM = os.getenv('IRM')

GATEKEEPER_URL = os.getenv('GATEKEEPER_URL')
