from os import environ
from authomatic.providers import oauth2

### Eve ###
MONGO_HOST = environ.get('MONGO_HOST', 'localhost')
MONGO_PORT = int(environ.get('MONGO_PORT', 27017))
MONGO_USERNAME = environ.get('MONGO_USERNAME', '')
MONGO_PASSWORD = environ.get('MONGO_PASSWORD', '')

MONGO_DBNAME = 'vigichiros'
X_DOMAINS=environ['FRONTEND_DOMAIN']
X_HEADERS=['Accept', 'Content-type', 'Authorization']
X_EXPOSE_HEADERS=X_HEADERS

RESOURCE_METHODS = ['GET', 'POST', 'DELETE']
ITEM_METHODS = ['GET', 'PATCH', 'PUT', 'DELETE']

DOMAIN = {
    'entries': {
    	'item_title': 'entry',
        'resource_methods': ['GET', 'POST'],
    	'schema': {
    	    'date': {'type': 'datetime', 'required': True},
            # 'picture': {'type': 'string', 'required': True},
            'picture': {'type': 'base64image', 'required': True},
    	    'location': {'type': 'point', 'required': True},
    	    'comment': {'type': 'string'}
    	}
    },
    'users': {
        'item_title': 'user',
        'resource_methods': ['GET'],
        'schema': {
            'name': {'type': 'string'},
            'email': {'type': 'string'}
        }
    }
}

### Authomatic ###
AUTHOMATIC = {
    'github': {
        'class_': oauth2.GitHub,
        'consumer_key': environ['GITHUB_API_KEY'],
        'consumer_secret': environ['GITHUB_API_SECRET'],
        'scope': oauth2.GitHub.user_info_scope,
        'access_headers': {'User-Agent': 'Awesome-Octocat-App'},
        '_apis': {
            'Get your events': ('GET', 'https://api.github.com/users/{user.username}/events'),
            'Get your watched repos': ('GET', 'https://api.github.com/user/subscriptions'),
        },
    },
    'google': {
        'class_': oauth2.Google,
        'consumer_key': environ['GOOGLE_API_KEY'],
        'consumer_secret': environ['GOOGLE_API_SECRET'],
        'scope': oauth2.Google.user_info_scope
    }
}

### App ###
SECRET_KEY = environ['SECRET_KEY']
FRONTEND_DOMAIN = environ['FRONTEND_DOMAIN']
PORT = int(environ.get('BACKEND_PORT', 8080))
BACKEND_DOMAIN = environ.get('BACKEND_DOMAIN', 'http://api.lvh.me:{}'.format(PORT))
