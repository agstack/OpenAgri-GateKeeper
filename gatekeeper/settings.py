import dj_database_url
import os

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

# geting from env var from now, but in the future this infos should
# come with the service registration post request
AVAILABLE_SERVICES = {
    'FarmCalendar':
    {
        'api': os.getenv('FARM_CALENDAR_API', 'http://127.0.0.1:8002/api/'),
        'post_auth': os.getenv('FARM_CALENDAR_POST_AUTH', 'http://127.0.0.1:8002/post_auth/')
    },
    'WeatherService': {
        'api': 'http://external_weather/api/',
        'post_auth': None,
    },
}
# same with this data, also cames in the service announcement
# in the service registration endpoint
REVERSE_PROXY_MAPPING = {
    'Farm': 'FarmCalendar',
    'FarmActivities': 'FarmCalendar',
    'FarmActivityTypes': 'FarmCalendar',
    'FarmAssets': 'FarmCalendar',
    'FarmPlants': 'FarmCalendar',
    'WeeklyWeatherForecast': 'WeatherService',
}

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['.localhost', '127.0.0.1', '[::1]']
EXTRA_ALLOWED_HOSTS = os.environ.get('EXTRA_ALLOWED_HOSTS', None)
if EXTRA_ALLOWED_HOSTS is not None:
    EXTRA_ALLOWED_HOSTS = EXTRA_ALLOWED_HOSTS.split(',')
    ALLOWED_HOSTS.extend(EXTRA_ALLOWED_HOSTS)


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
    "aegis.apps.AegisConfig",       # The app that contains auth logic, configured using the app's AppConfig.
]

THIRD_PARTY_APPS = [
    "crispy_forms",
    "crispy_bootstrap4",
    'django.contrib.sites',
    'rest_framework',
    'drf_yasg',
    'oauth2_provider',
]

INSTALLED_APPS = DEFAULT_APPS + LOCAL_APPS + THIRD_PARTY_APPS

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)


SITE_ID = 1

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap4"
CRISPY_TEMPLATE_PACK = "bootstrap4"

LOGIN_URL = "login/"
LOGOIN_REDIRECT_URL = 'aegis/dashboard/'  # Redirect to the login page
LOGOUT_REDIRECT_URL = 'login'  # Redirect to the login page after logging out


MIDDLEWARE = [
    'gatekeeper.custom_middleware.RequestLoggingMiddleware.RequestLoggingMiddleware',

    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    # 'gatekeeper.middleware.jwt_middleware',
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

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.mysql',
#         'NAME': os.getenv("DB_NAME"),
#         'USER': os.getenv("DB_USER"),
#         'PASSWORD': os.getenv("DB_PASS"),
#         'HOST': os.getenv("DB_HOST"),
#         'PORT': os.getenv("DB_PORT"),
#     },
# }

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

LANGUAGE_CODE = 'en-gn'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# STATIC_URL is the URL to use when referring to static files (like CSS, JavaScript, and images) in templates.
STATIC_URL = "/assets/"

# This setting defines the list of directories where Django will look for additional static files, in addition to
# each app's static folder.
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

# STATIC_ROOT is the directory where these static files will be collected when you run collectstatic.
STATIC_ROOT = os.path.join(BASE_DIR, 'assets')

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom user model replacing the default Django user model.
AUTH_USER_MODEL = 'aegis.DefaultAuthUserExtend'

DJANGO_PORT = os.getenv('APP_PORT', '8001')

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
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
        'oauth2_provider.contrib.rest_framework.OAuth2Authentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
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

OAUTH2_PROVIDER = {
    'ACCESS_TOKEN_EXPIRE_SECONDS': 36000,
    'REFRESH_TOKEN_EXPIRE_SECONDS': 864000,

    'SCOPES': {
        'read': 'Read scope',
        'write': 'Write scope',
        'groups': 'Access to your groups',
    }
}

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
