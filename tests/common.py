import requests
import json
import base64
import random
import string
import pytest
from pymongo import MongoClient
from bson import ObjectId
from eve.methods.post import post_internal

from vigiechiro import settings, app


db = MongoClient(settings.MONGO_HOST, settings.MONGO_PORT)[
    settings.MONGO_DBNAME]


def eve_post_internal(resource, payload):
    with app.test_request_context():
        result = post_internal(resource, payload)
        assert result[-1] == 201, result


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
        self.token = ''.join(
            random.choice(
                string.ascii_uppercase +
                string.digits) for x in range(32))
        self._user_id = AuthRequests.COUNT = AuthRequests.COUNT + 1
        payload = {
            'nom': 'nom_{}'.format(
                self._user_id), 'prenom': 'prenom_{}'.format(
                self._user_id), 'pseudo': 'pseudo_{}'.format(
                self._user_id), 'donnees_publiques': False, 'email': 'user_{}@email.com'.format(
                    self._user_id), 'role': role, 'tokens': [
                        self.token]}
        for key, value in fields:
            self.user[key] = value
        self.authorization = b'Basic ' + \
            base64.encodebytes(self.token.encode() + b':')
        eve_post_internal('utilisateurs', payload)
        self.user_id = str(
            db.utilisateurs.find_one({'pseudo': payload['pseudo']})['_id'])
        self.update_user()
        self.url = '/utilisateurs/' + self.user_id

    def finalizer(self):
        db.utilisateurs.remove({'_id': ObjectId(self.user_id)})

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
        r = self.get('/utilisateurs/' + self.user_id)
        assert r.status_code == 200, r.text
        self.user = r.json()
