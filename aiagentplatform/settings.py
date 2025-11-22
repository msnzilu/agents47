from pathlib import Path
import environ
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ======== ENVIRONMENT ========
env = environ.Env(
    DEBUG=(bool, False)
)
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))


# ================== SECRET KEY ==================
SECRET_KEY = env('SECRET_KEY')

# ================== DEBUG ==================
DEBUG = env('DEBUG')
SITE_NAME = env('SITE_NAME')
SITE_DOMAIN=env('SITE_DOMAIN')

# ================== ALLOWED HOSTS ==================
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])
LOGIN_URL = '/users/login/'

# ================================== SECURITY ==============================
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
# ================== CSRF TRUSTED ORIGINS ==================
CSRF_TRUSTED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS')


# ===================== APPLICATION DEFINITION ===============
INSTALLED_APPS = [

    # ===Default=======
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    # ==== Local Apps ==========
    'myadmin',
    'users',
    'chat',
    'agents',
    'integrations',
    'api',
    'embed',
    'webhooks',
    'analytics',
    'notifications',
    'security',

    # ======== External Apps ========
    'rest_framework',
    'channels',
    'celery',
    'drf_spectacular',
    'django_extensions'
]

AUTH_USER_MODEL = 'users.CustomUser'

# ================================== MIDDLEWARE ==============================
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware', 
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    # ================= Custom Middleware ============
    'security.middleware.SecurityHeadersMiddleware',        # Add security headers
    'security.middleware.RateLimitMiddleware',              # Rate limiting
    'security.middleware.SessionTimeoutMiddleware',         # Session timeout
    'security.middleware.CSRFTokenRotationMiddleware',      # CSRF rotation (optional)
    'security.middleware.RequestLoggingMiddleware',
]

ROOT_URLCONF = 'aiagentplatform.urls'



# ================================== TEMPLATES ==============================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'context_processors.site_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'aiagentplatform.wsgi.application'
ASGI_APPLICATION = 'aiagentplatform.asgi.application'


# ================================== DATABASE ==========================
import dj_database_url
DATABASES = {
    'default': dj_database_url.config(
        default=env('DATABASE_URL', default='sqlite:///db.sqlite3')
    )
}

# ================================== PASSWORD VALIDATION ==========================
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
    {'NAME': 'security.validators.PasswordStrengthValidator'},
    {'NAME': 'security.validators.PasswordHistoryValidator', 'OPTIONS': {'history_count': 5}},
]

AUTHENTICATION_BACKENDS = [
    'security.validators.TwoFactorAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]


# ============= INTERNATIONALIZATION ================================
LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# ==================== STATIC FILES ====================
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


# ==================== DEFAULT PRIMARY KEY FIELD TYPE ====================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ======= CELERY CONFIGURATIONS ======================
CELERY_BROKER_URL = env('REDIS_URL')
CELERY_RESULT_BACKEND = env('REDIS_URL')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'


# ==================== CHANNEL LAYERS ====================
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('redis', 6379)],
        },
    },
}


# =========API KEY CONFIGURATIONS ===============================
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')


# =============== REST Framework Configuration ===============
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}


# ================ API Documentation ======================================
SPECTACULAR_SETTINGS = {
    'TITLE': 'Agents47 API',
    'DESCRIPTION': 'REST API for managing AI agents and conversations',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

