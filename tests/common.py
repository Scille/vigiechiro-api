import requests
import random
import string
import pytest
from pymongo import MongoClient
from bson import ObjectId
from flask import g
from datetime import datetime, timedelta

from vigiechiro import settings, app
from vigiechiro.resources import utilisateurs as utilisateurs_resource

from wsgiref.handlers import format_date_time
from time import mktime


db = MongoClient(host=settings.MONGO_HOST).get_default_database()


def format_datetime(dt):
    stamp = mktime(dt.timetuple())
    return format_date_time(stamp)


def with_flask_context(f):
    def decorator(*args, **kwargs):
        with app.test_request_context():
            g.request_user = {'role': 'Administrateur'}
            return f(*args, **kwargs)
    return decorator


@pytest.fixture
def administrateur(request):
    auth = AuthRequests(role='Administrateur')
    request.addfinalizer(auth.finalizer)
    return auth


@pytest.fixture
def validateur(request):
    auth = AuthRequests(role='Validateur')
    request.addfinalizer(auth.finalizer)
    return auth


@pytest.fixture
def observateur(request):
    auth = AuthRequests(role='Observateur')
    request.addfinalizer(auth.finalizer)
    return auth


@pytest.fixture
def observateur_other(request):
    # It can be useful to have a friend to play with...
    auth = AuthRequests(role='Observateur')
    request.addfinalizer(auth.finalizer)
    return auth


class AuthRequests:
    COUNT = 0

    def __init__(self, role='Observateur', fields=[]):
        # Create a new user for the requests
        token_expire = datetime.utcnow() + timedelta(days=1)
        self.token = ''.join(random.choice(
                string.ascii_uppercase + string.digits) for x in range(32))
        self._user_id = AuthRequests.COUNT = AuthRequests.COUNT + 1
        payload = {
            'nom': 'nom_{}'.format(self._user_id),
            'prenom': 'prenom_{}'.format(self._user_id),
            'pseudo': 'pseudo_{}'.format(self._user_id),
            'donnees_publiques': False,
            'email': 'user_{}@email.com'.format(self._user_id),
            'role': role,
            'tokens': {self.token: token_expire}
        }
        for key, value in fields:
            self.user[key] = value
        @with_flask_context
        def insert_user():
            # Add additional_context to be allowed to modify tokens
            inserted = utilisateurs_resource.insert(payload, auto_abort=False,
                additional_context={'internal': True})
            assert inserted
            return inserted
        self.user = insert_user()
        self.user_id = str(self.user['_id'])
        # self.update_user()
        self.url = '/utilisateurs/' + self.user_id

    def finalizer(self):
        db.utilisateurs.delete_one({'_id': ObjectId(self.user_id)})

    def _auth(self, url, kwargs):
        kwargs['auth'] = (self.token, None)
        sep = '' if url.startswith('/') else '/'
        url = settings.BACKEND_DOMAIN + sep + url
        return (url, kwargs)

    def post(self, url, **kwargs):
        url, kwargs = self._auth(url, kwargs)
        return requests.request('post', url, **kwargs)

    def put(self, url, **kwargs):
        url, kwargs = self._auth(url, kwargs)
        return requests.request('put', url, **kwargs)

    def get(self, url, **kwargs):
        url, kwargs = self._auth(url, kwargs)
        return requests.request('get', url, **kwargs)

    def delete(self, url, **kwargs):
        url, kwargs = self._auth(url, kwargs)
        return requests.request('delete', url, **kwargs)

    def patch(self, url, **kwargs):
        url, kwargs = self._auth(url, kwargs)
        return requests.request('patch', url, **kwargs)

    def head(self, url, **kwargs):
        url, kwargs = self._auth(url, kwargs)
        return requests.request('head', url, **kwargs)

    def options(self, url, **kwargs):
        url, kwargs = self._auth(url, kwargs)
        return requests.request('options', url, **kwargs)

    def update_user(self):
        self.user = db.utilisateurs.find_one({'_id': self.user['_id']})
