from os import environ
from authomatic.providers import oauth2

from vigiechiro import utilisateurs

### App ###
SECRET_KEY = environ.get('SECRET_KEY', 'secret_for_test_only')
FRONTEND_DOMAIN = environ.get('FRONTEND_DOMAIN', 'http://www.lvh.me:9000')
PORT = int(environ.get('BACKEND_PORT', 8080))
BACKEND_DOMAIN = environ.get('BACKEND_DOMAIN', 'http://api.lvh.me:{}'.format(PORT))

MONGO_HOST = environ.get('MONGO_HOST', 'localhost')
MONGO_PORT = int(environ.get('MONGO_PORT', 27017))
MONGO_USERNAME = environ.get('MONGO_USERNAME', '')
MONGO_PASSWORD = environ.get('MONGO_PASSWORD', '')
MONGO_DBNAME = 'vigiechiro'

### Eve ###
X_DOMAINS=FRONTEND_DOMAIN
X_HEADERS=['Accept', 'Content-type', 'Authorization']
X_EXPOSE_HEADERS=X_HEADERS

RESOURCE_METHODS = ['GET', 'POST', 'DELETE']
ITEM_METHODS = ['GET', 'PATCH', 'PUT', 'DELETE']

DOMAIN = {
    'utilisateurs': utilisateurs.DOMAIN
}

### Authomatic ###
AUTHOMATIC = {
    'github': {
        'class_': oauth2.GitHub,
        'consumer_key': environ.get('GITHUB_API_KEY', ''),
        'consumer_secret': environ.get('GITHUB_API_SECRET', ''),
        'scope': oauth2.GitHub.user_info_scope,
        'access_headers': {'User-Agent': 'Awesome-Octocat-App'},
        '_apis': {
            'Get your events': ('GET', 'https://api.github.com/users/{user.username}/events'),
            'Get your watched repos': ('GET', 'https://api.github.com/user/subscriptions'),
        },
    },
    'google': {
        'class_': oauth2.Google,
        'consumer_key': environ.get('GOOGLE_API_KEY', ''),
        'consumer_secret': environ.get('GOOGLE_API_SECRET', ''),
        'scope': oauth2.Google.user_info_scope
    }
}
