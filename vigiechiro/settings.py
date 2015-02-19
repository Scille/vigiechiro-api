"""
    Settings
    ~~~~~~~~

    Global configuration of the project.
"""

from os import environ
from urllib.parse import quote
from authomatic.providers import oauth2
from enum import Enum


## vigiechiro ##
DEV_FAKE_AUTH = environ.get('DEV_FAKE_AUTH', 'False').lower() == 'true'
TOKEN_EXPIRE_TIME = 24 * 3600
ROLE_RULES = {
    'Lecteur': ['Lecteur'],
    'Observateur': ['Lecteur', 'Observateur'],
    'Validateur': ['Lecteur', 'Observateur', 'Validateur'],
    'Administrateur': ['Lecteur', 'Observateur', 'Validateur',
                       'Administrateur']}

# TODO : replace role by this enum system
class Roles(Enum):
    Lecteur = 0
    Observateur = 1
    Validateur = 2
    Administrateur = 3


### App ###
SECRET_KEY = environ.get('SECRET_KEY', 'secret_for_test_only')
FRONTEND_DOMAIN = environ.get('FRONTEND_DOMAIN', 'http://localhost:9000')
PORT = int(environ.get('BACKEND_PORT', 8080))
BACKEND_DOMAIN = environ.get(
    'BACKEND_DOMAIN', 'http://localhost:{}'.format(PORT))
ALLOWED_READ_ROLES = ['Lecteur']
ALLOWED_READ_ITEM_ROLES = ['Lecteur']

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

### Eve ###
X_DOMAINS = FRONTEND_DOMAIN
X_HEADERS = ['Accept', 'Content-type', 'Authorization', 'If-Match', 'Cache-Control']
X_EXPOSE_HEADERS = X_HEADERS

RESOURCE_METHODS = ['GET', 'POST', 'DELETE']
ITEM_METHODS = ['GET', 'PATCH', 'PUT', 'DELETE']

ALLOWED_READ_ROLES = ['Observateur']
ALLOWED_WRITE_ROLES = ['Administrateur']
ALLOWED_ITEM_READ_ROLES = ['Observateur']
ALLOWED_ITEM_WRITE_ROLES = ['Administrateur']

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
CELERY_BROKER_URL = environ.get('CELERY_BROKER_URL',
                                get_mongo_uri())

