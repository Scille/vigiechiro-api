import requests
import pytest
import base64
import json

from common import db
from vigiechiro import settings


def auth_header(token):
    return b'Basic ' + base64.encodebytes(token.encode() + b':')


def test_allowed():
    assert requests.get(settings.BACKEND_DOMAIN).status_code == 401


@pytest.fixture(scope="module")
def users_base(request):
    user1 = {'nom': 'Doe',
             'prenom': 'John',
             'telephone': '01 23 45 67 89',
             'donnes_publiques': False,
             'email': 'john.doe@gmail.com',
             'role': 'Observateur',
             'tokens': ['WPKQHC7LLNSI5KJAFEYXTD89W61RSDBO',
                        '6Z2GN5MJ8P1B234SP5RVJJTO2A2NOLF0']}
    db.utilisateurs.insert(user1)
    user2 = {'nom': 'van rossum',
             'prenom': 'guido',
             'email': 'guido@python.org',
             'donnes_publiques': True,
             'tags': ['Python', 'BDFL'],
             'organisation': 'Python fundation',
             'role': 'Administrateur',
             'tokens': ['IP12XQN81X4AX3NYP9TIRDUVDJS4KJXE']}
    db.utilisateurs.insert(user2)
    users = db.utilisateurs.find()

    def finalizer():
        for user in users:
            db.utilisateurs.remove({'_id': user['_id']})
    # request.addfinalizer(finalizer)
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


@pytest.mark.xfail
def test_user_route(users_base):
    user = users_base[0]
    r = requests.get(settings.BACKEND_DOMAIN + '/utilisateurs/moi',
                     headers={'Authorization': auth_header(user['tokens'][0])})
    assert r.status_code == 200
    content = r.json()
    for key in ['nom', 'email']:
        assert users_base[key] == content[key]


@pytest.mark.xfail
def test_rights(users_base):
    me = users_base[0]
    auth = auth_header(me['tokens'][0])
    payload = {'donnes_publiques': True}
    # Change data for myself is allowed...
    r = requests.get(settings.BACKEND_DOMAIN + '/utilisateurs/moi',
                     headers={
                         'Authorization': auth, 'Content-type': 'application/json'},
                     data=json.dumps(payload))
    assert r.status_code == 200
    assert r.json()['donnes_publiques'] == True
    # ...but I can't change for others !
    admin = users_base[1]
    r = requests.get(settings.BACKEND_DOMAIN + '/utilisateurs/' + admin['_id'],
                     headers={
                         'Authorization': auth, 'Content-type': 'application/json'},
                     data=json.dumps(payload))
    assert r.status_code == 403
    # Same thing, cannot change my own rights
    payload = {'role': 'Administrateur'}
    r = requests.get(settings.BACKEND_DOMAIN + '/utilisateurs/moi',
                     headers={
                         'Authorization': auth, 'Content-type': 'application/json'},
                     data=json.dumps(payload))
    assert r.status_code == 403
    # Of courses, admin can
    payload = {'role': 'Validateur'}
    r = requests.get(settings.BACKEND_DOMAIN + '/utilisateurs/' + me['_id'],
                     headers={'Authorization': auth_header(admin['tokens'][0]),
                              'Content-type': 'application/json'},
                     data=json.dumps(payload))
    assert r.status_code == 200
    assert r.json()['role'] == 'Validateur'
