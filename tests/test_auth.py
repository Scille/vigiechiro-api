import requests
import pytest
from bson import ObjectId
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

from .common import db, observateur
from .test_utilisateurs import users_base
from vigiechiro import settings


PROTECTED_URL = settings.BACKEND_DOMAIN + '/moi'


def test_script_worker():
    r = requests.get(PROTECTED_URL, auth=(settings.SCRIPT_WORKER_TOKEN, None))
    assert r.status_code == 200
    assert r.json()['role'] == 'Administrateur'


def test_allowed():
    assert requests.get(PROTECTED_URL).status_code == 401


def test_token_access(users_base):
    user = users_base[0]
    for token in user['tokens']:
        r = requests.get(PROTECTED_URL, auth=(token, None))
        assert r.status_code == 200
    dummy_token = 'J9QV87RDUW9UFE8D6WSKXYYZ6CGBG17G'
    r = requests.get(PROTECTED_URL, auth=(dummy_token, None))
    assert r.status_code == 401


def test_expiration_token(observateur):
    # Set the token to expiration
    token_expire = token_expire = datetime.utcnow() - timedelta(seconds=1)
    db.utilisateurs.update({'_id': ObjectId(observateur.user_id)},
                           {'$set': {'tokens.'+observateur.token: token_expire}})
    r = observateur.get('/moi')
    assert r.status_code == 401, r.text


def test_single_login():
    r = requests.get(settings.BACKEND_DOMAIN + '/login/google',
                     allow_redirects=False)
    assert r.status_code == 302
    assert 'Location' in r.headers
    # Replace '#' in the location to let urllib parse correctly
    location = r.headers['Location'].replace('#', '!')
    qs = parse_qs(urlparse(location).query)
    assert 'token' in qs
    token = qs['token'][0]
    r = requests.get(PROTECTED_URL, auth=(token, None))
    assert r.status_code == 200, r.text
    resource = r.json()
    print(resource)
    for field in ['_id', '_etag', '_created', '_updated']:
        assert field in resource
    return token

def test_multi_login():
    first_token = test_single_login()
    # Test multi-login as well, both should work at the same time
    second_token = test_single_login()
    for token in [first_token, second_token]:
        r = requests.get(PROTECTED_URL, auth=(token, None))
        assert r.status_code == 200, r.text


def test_logout(observateur):
    r = observateur.post('/logout')
    assert r.status_code == 200
    r = observateur.get('/moi')
    assert r.status_code == 401


def test_cors(observateur):
    for method in ['GET', 'PATCH']:
        r = observateur.options('/moi', headers={
            'Access-Control-Request-Headers': 'accept, cache-control, authorization, content-type',
            'Access-Control-Request-Method': method
        })
        assert r.status_code == 200, r.text
        assert 'Access-Control-Allow-Headers' in r.headers
        assert r.headers['Access-Control-Allow-Headers'] == 'ACCEPT, CONTENT-TYPE, AUTHORIZATION, IF-MATCH, IF-NONE-MATCH, CACHE-CONTROL'
        assert 'Access-Control-Allow-Methods' in r.headers
        assert r.headers['Access-Control-Allow-Methods'] == 'GET, PATCH'
        assert 'Access-Control-Allow-Origin' in r.headers
        assert r.headers['Access-Control-Allow-Origin'] == settings.FRONTEND_DOMAIN
