from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

def env_bool(name, default=False):
    return os.getenv(name, str(default)).lower() in {'1','true','yes','on'}

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'unsafe-development-key-change-me')
DEBUG = env_bool('DJANGO_DEBUG', False)
ALLOWED_HOSTS = [x.strip() for x in os.getenv('DJANGO_ALLOWED_HOSTS','127.0.0.1,localhost').split(',') if x.strip()]
CSRF_TRUSTED_ORIGINS = [x.strip() for x in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS','').split(',') if x.strip()]

INSTALLED_APPS = [
 'django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions',
 'django.contrib.messages','django.contrib.staticfiles','django.contrib.postgres',
 'accounts','research',
]
MIDDLEWARE = [
 'django.middleware.security.SecurityMiddleware','whitenoise.middleware.WhiteNoiseMiddleware',
 'django.contrib.sessions.middleware.SessionMiddleware','django.middleware.locale.LocaleMiddleware',
 'django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware',
 'django.contrib.auth.middleware.AuthenticationMiddleware','accounts.middleware.EnabledUserMiddleware','django.contrib.messages.middleware.MessageMiddleware',
 'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF='zoha.urls'
TEMPLATES=[{
 'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,
 'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth',
 'django.contrib.messages.context_processors.messages','research.context_processors.zoha_context']},
}]
WSGI_APPLICATION='zoha.wsgi.application'
ASGI_APPLICATION='zoha.asgi.application'

if os.getenv('DB_ENGINE','postgresql') == 'sqlite':
    DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'db.sqlite3'}}
else:
    DATABASES={'default':{'ENGINE':'django.db.backends.postgresql','NAME':os.getenv('DB_NAME','zohaonline_db'),
      'USER':os.getenv('DB_USER','zohaonline_user'),'PASSWORD':os.getenv('DB_PASSWORD',''),
      'HOST':os.getenv('DB_HOST','127.0.0.1'),'PORT':os.getenv('DB_PORT','5432'),
      'CONN_MAX_AGE':60,'CONN_HEALTH_CHECKS':True,'OPTIONS':{'connect_timeout':10}}}

AUTH_PASSWORD_VALIDATORS=[
 {'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
 {'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},
 {'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},
 {'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE='fa-ir'
TIME_ZONE=os.getenv('TIME_ZONE','Asia/Tehran')
USE_I18N=True
USE_TZ=True
AUTH_USER_MODEL='accounts.User'
LOGIN_URL='login'; LOGIN_REDIRECT_URL='dashboard'; LOGOUT_REDIRECT_URL='login'

# Optional path-prefix deployment, e.g. http://server/zohaonline/
URL_PREFIX = os.getenv('DJANGO_URL_PREFIX', '').strip().strip('/')
APP_BASE_PATH = f'/{URL_PREFIX}' if URL_PREFIX else ''
STATIC_URL = f'{APP_BASE_PATH}/static/'
STATIC_ROOT = BASE_DIR/'staticfiles'
STATICFILES_DIRS = [BASE_DIR/'static']
MEDIA_URL = f'{APP_BASE_PATH}/media/'
MEDIA_ROOT = BASE_DIR/'media'

# Keep this app's cookies isolated from other applications on the same host.
SESSION_COOKIE_NAME = 'zohaonline_sessionid'
CSRF_COOKIE_NAME = 'zohaonline_csrftoken'
SESSION_COOKIE_PATH = f'{APP_BASE_PATH}/' if APP_BASE_PATH else '/'
CSRF_COOKIE_PATH = f'{APP_BASE_PATH}/' if APP_BASE_PATH else '/'
STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
          'staticfiles':{'BACKEND':'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
DATA_UPLOAD_MAX_MEMORY_SIZE=25*1024*1024
FILE_UPLOAD_MAX_MEMORY_SIZE=10*1024*1024
SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO','https')
SECURE_SSL_REDIRECT=env_bool('SECURE_SSL_REDIRECT',False)
SESSION_COOKIE_SECURE=env_bool('SESSION_COOKIE_SECURE',False)
CSRF_COOKIE_SECURE=env_bool('CSRF_COOKIE_SECURE',False)
X_FRAME_OPTIONS='DENY'

# Zoha 2.7 public/AI integration settings
ZOHA_PUBLIC_EMAIL = os.getenv('ZOHA_PUBLIC_EMAIL', 'info@zohaonline.ir')
ZOHA_CHANNEL_URL = os.getenv('ZOHA_CHANNEL_URL', '').strip()
ZOHA_IMAGE_API_URL = os.getenv('ZOHA_IMAGE_API_URL', '').strip()
ZOHA_IMAGE_API_KEY = os.getenv('ZOHA_IMAGE_API_KEY', '').strip()
ZOHA_QURAN_REFERENCE_URL = os.getenv('ZOHA_QURAN_REFERENCE_URL', 'https://quran.inoor.ir/fa/home')
ZOHA_HADITH_REFERENCE_URL = os.getenv('ZOHA_HADITH_REFERENCE_URL', 'https://hadith.inoor.ir/')
ZOHA_POETRY_REFERENCE_URL = os.getenv('ZOHA_POETRY_REFERENCE_URL', 'https://ganjoor.net/')
