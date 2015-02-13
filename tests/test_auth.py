import requests
import pytest
from bson import ObjectId
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

from common import db, observateur
from vigiechiro import settings
from test_utilisateur import users_base


PROTECTED_URL = settings.BACKEND_DOMAIN + '/utilisateurs/moi'


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
    r = observateur.get('/utilisateurs/moi')
    assert r.status_code == 401, r.text
    content = r.json()


def test_single_login():
    r = requests.get(settings.BACKEND_DOMAIN + '/login/google',
                     allow_redirects=False)
    assert r.status_code == 302
    assert 'Location' in r.headers
    # Replace '#' in the location to let urllib parse correctly
    location = r.headers['Location'].replace('#', '!')
    qs = parse_qs(urlparse(location).query)
    print(qs)
    assert 'token' in qs
    token = qs['token'][0]
    r = requests.get(PROTECTED_URL, auth=(token, None))
    assert r.status_code == 200, r.text
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
    r = observateur.get('/utilisateurs/moi')
    assert r.status_code == 401

