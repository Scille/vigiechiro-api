import requests
import pytest
import base64
import json

from common import db, observateur, administrateur, eve_post_internal
from vigiechiro import settings


def auth_header(token):
    return b'Basic ' + base64.encodebytes(token.encode() + b':')


def test_allowed():
    assert requests.get(settings.BACKEND_DOMAIN).status_code == 401


@pytest.fixture(scope="module")
def users_base(request):
    user1 = {'nom': 'Doe',
             'prenom': 'John',
             'pseudo': 'n00b',
             'telephone': '01 23 45 67 89',
             'donnees_publiques': False,
             'email': 'john.doe@gmail.com',
             'role': 'Observateur',
             'tokens': ['WPKQHC7LLNSI5KJAFEYXTD89W61RSDBO',
                        '6Z2GN5MJ8P1B234SP5RVJJTO2A2NOLF0']}
    eve_post_internal('utilisateurs', user1)
    user2 = {'nom': 'van rossum',
             'prenom': 'guido',
             'pseudo': 'gr0k',
             'email': 'guido@python.org',
             'donnees_publiques': True,
             'tags': ['Python', 'BDFL'],
             'organisation': 'Python fundation',
             'role': 'Administrateur',
             'tokens': ['IP12XQN81X4AX3NYP9TIRDUVDJS4KJXE']}
    eve_post_internal('utilisateurs', user2)
    users = [user for user in db.utilisateurs.find()]

    def finalizer():
        for user in [user1, user2]:
            db.utilisateurs.remove({'pseudo': user['pseudo']})
    request.addfinalizer(finalizer)
    return users


def test_token_access(users_base):
    user = users_base[0]
    for token in user['tokens']:
        r = requests.get(settings.BACKEND_DOMAIN,
                         auth=(token, None))
        assert r.status_code == 200
    dummy_token = 'J9QV87RDUW9UFE8D6WSKXYYZ6CGBG17G'
    r = requests.get(settings.BACKEND_DOMAIN,
                     headers={'Authorization': auth_header(dummy_token)})
    assert r.status_code == 401


def test_user_route(users_base):
    user = users_base[0]
    r = requests.get(settings.BACKEND_DOMAIN + '/utilisateurs/moi',
                     headers={'Authorization': auth_header(user['tokens'][0])})
    assert r.status_code == 200
    content = r.json()
    for key in ['nom', 'email']:
        assert user[key] == content[key]


def test_rights(observateur, administrateur):
    # Change data for myself is allowed...
    payload = {'donnees_publiques': True}
    r = observateur.patch(
        observateur.url,
        headers={
            'If-Match': observateur.user['_etag']},
        json=payload)
    assert r.status_code == 200, r.text
    observateur.update_user()
    assert observateur.user['donnees_publiques']
    # ...but I can't change for others !
    r = observateur.patch(administrateur.url,
                          headers={'If-Match': administrateur.user['_etag']},
                          json=payload)
    assert r.status_code == 403, r.text
    # Same thing, cannot change my own rights
    r = observateur.patch(observateur.url,
                          headers={'If-Match': observateur.user['_etag']},
                          json={'role': 'Administrateur'})
    assert r.status_code == 403, r.text
    # Of courses, admin can
    r = administrateur.patch(observateur.url,
                             headers={'If-Match': observateur.user['_etag']},
                             json={'role': 'Validateur'})
    assert r.status_code == 200, r.text
    observateur.update_user()
    assert observateur.user['role'] == 'Validateur'


def test_readonly_fields(observateur, administrateur):
    payloads = [{'role': 'Administrateur'},
                {'email': 'new@mail.com'},
                {'pseudo': 'new_me!'}]
    for payload in payloads:
        r = observateur.patch(observateur.url,
                              headers={'If-Match': observateur.user['_etag']},
                              json=payload)
        assert r.status_code == 403, r.text
        # Admin can do everything !
        r = administrateur.patch(
            administrateur.url,
            headers={
                'If-Match': administrateur.user['_etag']},
            json=payload)
        administrateur.update_user()
        assert r.status_code == 200, r.text


def test_internal_resource(observateur):
    r = observateur.get(observateur.url)
    assert r.status_code == 200
    assert 'tokens' not in r.json()
    payload = {'tokens': ['7U5L5J8B7BEDH5MFOHZ8D2834AUNTPXI']}
    r = observateur.patch(observateur.url,
                          headers={'If-Match': observateur.user['_etag']},
                          json=payload)
    assert r.status_code == 403, r.text
