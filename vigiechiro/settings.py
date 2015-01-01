"""
    Settings
    ~~~~~~~~

    Global configuration of the project.
"""

from os import environ
from authomatic.providers import oauth2
from enum import Enum


## vigiechiro ##
ROLE_RULES = {
    'Lecteur': ['Lecteur'], 'Observateur': [
        'Lecteur', 'Observateur'], 'Validateur': [
            'Lecteur', 'Observateur', 'Validateur'], 'Administrateur': [
                'Lecteur', 'Observateur', 'Validateur', 'Administrateur']}
# TODO : replace role by this enum system


class Roles(Enum):
    Lecteur = 0
    Observateur = 1
    Validateur = 2
    Administrateur = 3


### App ###
SECRET_KEY = environ.get('SECRET_KEY', 'secret_for_test_only')
FRONTEND_DOMAIN = environ.get('FRONTEND_DOMAIN', 'http://www.lvh.me:9000')
PORT = int(environ.get('BACKEND_PORT', 8080))
BACKEND_DOMAIN = environ.get(
    'BACKEND_DOMAIN', 'http://api.lvh.me:{}'.format(PORT))
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
MONGO_DBNAME = 'vigiechiro'

### Eve ###
X_DOMAINS = FRONTEND_DOMAIN
X_HEADERS = ['Accept', 'Content-type', 'Authorization']
X_EXPOSE_HEADERS = X_HEADERS

RESOURCE_METHODS = ['GET', 'POST', 'DELETE']
ITEM_METHODS = ['GET', 'PATCH', 'PUT', 'DELETE']

ALLOWED_READ_ROLES = ['Observateur']
ALLOWED_WRITE_ROLES = ['Administrateur']
ALLOWED_ITEM_READ_ROLES = ['Observateur']
ALLOWED_ITEM_WRITE_ROLES = ['Administrateur']

### Authomatic ###
AUTHOMATIC = {
    'github': {
        'class_': oauth2.GitHub,
        'consumer_key': environ.get(
            'GITHUB_API_KEY',
            ''),
        'consumer_secret': environ.get(
            'GITHUB_API_SECRET',
            ''),
        'scope': oauth2.GitHub.user_info_scope,
        'access_headers': {
            'User-Agent': 'Awesome-Octocat-App'},
        '_apis': {
            'Get your events': (
                'GET',
                'https://api.github.com/users/{user.username}/events'),
            'Get your watched repos': (
                'GET',
                'https://api.github.com/user/subscriptions'),
        },
    },
    'google': {
        'class_': oauth2.Google,
        'consumer_key': environ.get(
            'GOOGLE_API_KEY',
            ''),
        'consumer_secret': environ.get(
            'GOOGLE_API_SECRET',
            ''),
        'scope': oauth2.Google.user_info_scope}}

### S3 ###
AWS_KEY = environ.get('AWS_KEY', '')
AWS_SECRET = environ.get('AWS_SECRET', '')
S3_BUCKET = environ.get('S3_BUCKET', '')
