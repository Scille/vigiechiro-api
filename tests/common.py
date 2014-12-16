import requests
import json
import base64
import random
import string
import pytest
from pymongo import MongoClient

from vigiechiro import settings


db = MongoClient(settings.MONGO_HOST, settings.MONGO_PORT)[
    settings.MONGO_DBNAME]


@pytest.fixture
def administrateur(request):
    auth = AuthRequests(role='Administrateur')
    request.addfinalizer(auth.finalizer)
    return auth


@pytest.fixture
def observateur(request):
    auth = AuthRequests(role='Observateur')
    request.addfinalizer(auth.finalizer)
    return auth


@pytest.fixture
def validateur(request):
    auth = AuthRequests(role='Validateur')
    request.addfinalizer(auth.finalizer)
    return auth


class AuthRequests:
    COUNT = 0

    def __init__(self, role='Observateur', fields=[]):
        # Create a new user for the requests
        self.token = ''.join(random.choice(string.ascii_uppercase + string.digits)
                             for x in range(32))
        self.user_id = AuthRequests.COUNT
        AuthRequests.COUNT + 1
        self.user = {'nom': 'nom_{}'.format(self.user_id),
                     'prenom': 'prenom_{}'.format(self.user_id),
                     'donnes_publiques': False,
                     'email': 'user_{}@email.com'.format(self.user_id),
                     'role': role,
                     'tokens': [self.token]}
        for key, value in fields:
            self.user[key] = value
        self.authorization = b'Basic ' + \
            base64.encodebytes(self.token.encode() + b':')
        self.user['_id'] = db.utilisateurs.insert(self.user)

    def finalizer(self):
        db.utilisateurs.remove({'_id': self.user['_id']})

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
