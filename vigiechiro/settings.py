"""
    Settings
    ~~~~~~~~

    Global configuration of the project.
"""

from os import environ
from authomatic.providers import oauth2


# RFC 1123 (ex RFC 822)
DATE_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'

SCRIPT_WORKER_EXPIRES = int(environ.get('SCRIPT_WORKER_EXPIRES', 100 * 365))
SCRIPT_WORKER_TOKEN = environ.get('SCRIPT_WORKER_TOKEN', 'token_for_test_only')

## vigiechiro ##
DEV_FAKE_AUTH = environ.get('DEV_FAKE_AUTH', 'False').lower() == 'true'
DEV_FAKE_S3_URL = environ.get('DEV_FAKE_S3_URL', None)
# into seconds
TOKEN_EXPIRE_TIME = 14 * 24 * 3600
ROLE_RULES = {
    'Lecteur': ['Lecteur'],
    'Observateur': ['Lecteur', 'Observateur'],
    'Validateur': ['Lecteur', 'Observateur', 'Validateur'],
    'Administrateur': ['Lecteur', 'Observateur', 'Validateur',
                       'Administrateur']}
TADARIDA_D_OPTS = environ.get('TADARIDA_D_OPTS', "")
TADARIDA_C_OPTS = environ.get('TADARIDA_C_OPTS', "")
try:
    TADARIDA_C_BATCH_SIZE = int(environ['TADARIDA_C_BATCH_SIZE'])
except (ValueError, KeyError):
    TADARIDA_C_BATCH_SIZE = 1000

### App ###
SECRET_KEY = environ.get('SECRET_KEY', 'secret_for_test_only')
BACKEND_URL_PREFIX = environ.get('BACKEND_URL_PREFIX', '')
assert not BACKEND_URL_PREFIX or BACKEND_URL_PREFIX.startswith('/')
FRONTEND_HOSTED = environ.get('FRONTEND_HOSTED', False)
FRONTEND_HOSTED_REDIRECT_URL = environ.get('FRONTEND_HOSTED_REDIRECT_URL', '')
PORT = int(environ.get('BACKEND_PORT', 8080))
BACKEND_DOMAIN = environ.get(
    'BACKEND_DOMAIN', 'http://localhost:{}{}'.format(PORT, BACKEND_URL_PREFIX))
FRONTEND_DOMAIN = environ.get('FRONTEND_DOMAIN',
    'http://localhost:%s' % PORT if FRONTEND_HOSTED else 'http://localhost:9000')
REQUESTS_TIMEOUT = int(environ.get('REQUESTS_TIMEOUT', 90))

### MongoDB ###
MONGO_HOST = MONGO_URI = environ.get('MONGO_HOST', 'mongodb://localhost:27017/vigiechiro')

### CORS ###
X_DOMAINS = environ.get('CORS_ORIGIN', FRONTEND_DOMAIN)
X_HEADERS = ['Accept', 'Content-type', 'Authorization', 'If-Match', 'If-None-Match', 'Cache-Control']
X_EXPOSE_HEADERS = X_HEADERS

### Authomatic ###
AUTHOMATIC = {
    'google': {
        'class_': oauth2.Google,
        'consumer_key': environ.get('GOOGLE_API_KEY', ''),
        'consumer_secret': environ.get('GOOGLE_API_SECRET', ''),
        'scope': oauth2.Google.user_info_scope
    },
    'facebook': {
        'class_': oauth2.Facebook,
        'consumer_key': environ.get('FACEBOOK_API_KEY', ''),
        'consumer_secret': environ.get('FACEBOOK_API_SECRET', ''),
        # 'scope': oauth2.Facebook.user_info_scope
        'scope': ['email', 'public_profile']
    }
}

### S3 ###
AWS_S3_BUCKET = environ.get('AWS_S3_BUCKET', '')
AWS_ACCESS_KEY_ID = environ.get('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = environ.get('AWS_SECRET_ACCESS_KEY', '')

### Flask Mail ###
MAIL_SERVER = environ.get('MAIL_SERVER')
MAIL_PORT = environ.get('MAIL_PORT')
MAIL_DEBUG = environ.get('MAIL_DEBUG', 'false').lower() == 'true'
MAIL_USERNAME = environ.get('MAIL_USERNAME')
MAIL_PASSWORD = environ.get('MAIL_PASSWORD')
MAIL_DEFAULT_SENDER = environ.get('MAIL_DEFAULT_SENDER')
MAIL_MODE = environ.get('MAIL_MODE')

TASK_PARTICIPATION_BATCH_SIZE = int(environ.get('TASK_PARTICIPATION_BATCH_SIZE', 100))
TASK_PARTICIPATION_KEEP_TMP_DIR = environ.get('TASK_PARTICIPATION_KEEP_TMP_DIR', 'false').lower() == 'true'
TASK_PARTICIPATION_PARALLELE_POOL = int(environ.get('TASK_PARTICIPATION_PARALLELE_POOL', 10))
TASK_PARTICIPATION_DATASTORE_CACHE = environ.get('TASK_PARTICIPATION_DATASTORE_CACHE', None)
TASK_PARTICIPATION_DATASTORE_USE_SYMLINKS = environ.get('TASK_PARTICIPATION_DATASTORE_USE_SYMLINKS', 'false').lower() == 'true'
TASK_PARTICIPATION_UPLOAD_GENERATED_FILES = environ.get('TASK_PARTICIPATION_UPLOAD_GENERATED_FILES', 'true').lower() == 'true'
TASK_PARTICIPATION_MAX_RETRY = int(environ.get('TASK_PARTICIPATION_MAX_RETRY', 1))
TASK_PARTICIPATION_EXTRACT_BACKEND = environ.get("TASK_PARTICIPATION_EXTRACT_BACKEND", "unzip")
assert TASK_PARTICIPATION_EXTRACT_BACKEND in ("unzip", "7zip")
TASK_PARTICIPATION_GENERATE_OBSERVATION_CSV = environ.get('TASK_PARTICIPATION_GENERATE_OBSERVATION_CSV', 'false').lower() == 'true'
TASK_PARTICIPATION_SETTLE_DB_SLEEP = int(environ.get('TASK_PARTICIPATION_SETTLE_DB_SLEEP', 0))
