"""
Configuración principal del proyecto Django.
Las credenciales se leen desde variables de entorno (.env).
"""
from pathlib import Path

import dj_database_url
from decouple import config

# Ruta base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# Clave secreta: en producción debe venir desde variables de entorno (.env).
SECRET_KEY = config(
    'SECRET_KEY',
    default='django-insecure-local-development-key-change-me',
)

# DEBUG=True solo en desarrollo local; False en producción (Render)
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '.onrender.com']

# Aplicaciones instaladas
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'inventario',  # App principal del supermercado
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Base de datos: SQLite en desarrollo, PostgreSQL/Supabase en producción (Render)
if DEBUG:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': dj_database_url.config(default=config('DATABASE_URL')),
    }

# Validación de contraseñas (preparado para cuando agreguemos login)
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Zona horaria de Bogotá para fechas de ventas
LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

# Archivos estáticos (CSS, JS, imágenes)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Paginación del inventario
PRODUCTOS_POR_PAGINA = 15

# Umbrales de stock bajo (para colores e indicadores)
STOCK_CRITICO = 10
STOCK_BAJO = 20
STOCK_ATENCION = 30

# Sesión: nunca cerrar por inactividad (usuario adulto mayor)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_AGE = 60 * 60 * 24 * 365 * 10  # 10 años

# Clave para entrar a las secciones internas (Inventario e Historial).
# El valor es un hash PBKDF2 de Django, no la contrasena en texto plano.
INTERNAL_ACCESS_PASSWORD_HASH = config(
    'INTERNAL_ACCESS_PASSWORD_HASH',
    default='pbkdf2_sha256$1000000$WfTX2hFVJdOhtu0WJIC6ki$CSWqQi0vC5tAmF6rmiDzINHbbwOLUUxFSJOHpte2q1I=',
)
INTERNAL_ACCESS_SESSION_SECONDS = config(
    'INTERNAL_ACCESS_SESSION_SECONDS',
    default=60 * 60 * 4,
    cast=int,
)
