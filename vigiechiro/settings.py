"""
    Settings
    ~~~~~~~~

    Global configuration of the project.
"""

from os import environ
from urllib.parse import quote
from authomatic.providers import oauth2
from enum import Enum


# RFC 1123 (ex RFC 822)
DATE_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'

SCRIPT_WORKER_EXPIRES = int(environ.get('SCRIPT_WORKER_EXPIRES', 100 * 365))
SCRIPT_WORKER_TOKEN = environ.get('SCRIPT_WORKER_TOKEN', 'token_for_test_only')

## vigiechiro ##
DEV_FAKE_AUTH = environ.get('DEV_FAKE_AUTH', 'False').lower() == 'true'
DEV_FAKE_S3_URL = environ.get('DEV_FAKE_S3_URL', None)
TOKEN_EXPIRE_TIME = 24 * 3600
ROLE_RULES = {
    'Lecteur': ['Lecteur'],
    'Observateur': ['Lecteur', 'Observateur'],
    'Validateur': ['Lecteur', 'Observateur', 'Validateur'],
    'Administrateur': ['Lecteur', 'Observateur', 'Validateur',
                       'Administrateur']}
TADARIDA_D_CONCURENCY = environ.get('TADARIDA_D_CONCURRENCY', 1)

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


### Redis ###
REDIS_PORT = environ.get('REDIS_PORT', 6379)
REDIS_HOST = environ.get('REDIS_HOST', 'localhost')

### MongoDB ###
MONGO_HOST = environ.get('MONGO_HOST', 'localhost')
MONGO_PORT = int(environ.get('MONGO_PORT', 27017))
MONGO_USERNAME = environ.get('MONGO_USERNAME', '')
MONGO_PASSWORD = environ.get('MONGO_PASSWORD', '')
MONGO_DBNAME = environ.get('MONGO_DBNAME', 'vigiechiro')
def get_mongo_uri():
    basepart = "{host}:{port}/{database}".format(
        host=MONGO_HOST, port=MONGO_PORT, database=MONGO_DBNAME)
    if not MONGO_USERNAME:
        return 'mongodb://' + basepart
    else:
        return "mongodb://{username}:{password}@{basepart}".format(
            username=quote(MONGO_USERNAME), password=quote(MONGO_PASSWORD),
            basepart=basepart)

### CORS ###
X_DOMAINS = FRONTEND_DOMAIN
X_HEADERS = ['Accept', 'Content-type', 'Authorization', 'If-Match', 'Cache-Control']
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
        'scope': oauth2.Facebook.user_info_scope
    }
}

### S3 ###
AWS_S3_BUCKET = environ.get('AWS_S3_BUCKET', '')
AWS_ACCESS_KEY_ID = environ.get('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = environ.get('AWS_SECRET_ACCESS_KEY', '')

### Celery broker ###
CELERY_BROKER_URL = environ.get('CELERY_BROKER_URL', get_mongo_uri())
HIREFIRE_TOKEN = environ.get('HIREFIRE_TOKEN', 'development')
