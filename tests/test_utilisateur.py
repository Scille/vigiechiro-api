import requests
import pytest
import base64
import json

from common import db, observateur, validateur, administrateur, eve_post_internal
from vigiechiro import settings
from test_protocole import protocoles_base
from test_taxon import taxons_base


def auth_header(token):
    return b'Basic ' + base64.encodebytes(token.encode() + b':')


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
        db.utilisateurs.remove()
    request.addfinalizer(finalizer)
    return users


def test_allowed():
    assert requests.get(settings.BACKEND_DOMAIN).status_code == 401


def test_dummy_user(administrateur):
    for dummy in ['549982ae13adf2435290074b', 'dummy', '01234', ' ', '/']:
        r = administrateur.get('/utilisateurs/' + dummy)
        assert r.status_code == 404, r.text


def test_dummy_role(administrateur):
    for dummy_role in ['Administrateur ', ' ', 'observateur']:
        r = administrateur.patch('/utilisateurs/moi',
                                 headers={'If-Match': administrateur.user['_etag']},
                                 json={'role': dummy_role})
        assert r.status_code == 422, r.text


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


def test_user_route(observateur):
    r = observateur.get('/utilisateurs/moi')
    assert r.status_code == 200, r.text
    content = r.json()
    for key in ['nom', 'email']:
        assert observateur.user[key] == content[key]
    r = observateur.patch('/utilisateurs/moi',
                          headers={'If-Match': content['_etag']},
                          json={'commentaire': 'New comment'})
    assert r.status_code == 200, r.text
    observateur.update_user()
    assert observateur.user['commentaire'] == 'New comment'


def test_rights_write(observateur, administrateur):
    # Change data for myself is allowed...
    payload = {'donnees_publiques': True}
    r = observateur.patch(observateur.url,
                          headers={'If-Match': observateur.user['_etag']},
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
    assert r.status_code == 422, r.text
    # Of courses, admin can
    r = administrateur.patch(observateur.url,
                             headers={'If-Match': observateur.user['_etag']},
                             json={'role': 'Validateur'})
    assert r.status_code == 200, r.text
    observateur.update_user()
    assert observateur.user['role'] == 'Validateur'
    # Finally, try to change various allowed stuffs
    etag = observateur.user['_etag']
    for payload in [{'pseudo': 'my new pseudo !'},
                    {'email': 'new@email.com'},
                    {'nom': 'newLastName', 'prenom': 'newFirstName'}]:
        r = observateur.patch(observateur.url,
                              headers={'If-Match': etag},
                              json=payload)
        assert r.status_code == 200, r.text
        etag = r.json()['_etag']


def test_rigths_read(observateur, validateur):
    # Observateur cannot list or see others user's profile
    r = observateur.get('/utilisateurs')
    assert r.status_code == 403, r.text
    r = observateur.get(validateur.url)
    assert r.status_code == 403, r.text
    # Validateur and upper roles can see all users
    r = validateur.get('/utilisateurs')
    assert r.status_code == 200, r.text
    r = validateur.get(observateur.url)
    assert r.status_code == 200, r.text


def test_readonly_fields(observateur, administrateur):
    payloads = [{'role': 'Administrateur'}]
    for payload in payloads:
        r = observateur.patch(observateur.url,
                              headers={'If-Match': observateur.user['_etag']},
                              json=payload)
        assert r.status_code == 422, r.text
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
    payloads = [{'tokens': ['7U5L5J8B7BEDH5MFOHZ8D2834AUNTPXI']},
                {'github_id': '1872655'},
                {'facebook_id': '1872655'},
                {'google_id': '1872655'}]
    for payload in payloads:
        r = observateur.patch(observateur.url,
                              headers={'If-Match': observateur.user['_etag']},
                              json=payload)
        print(r.text)
        assert r.status_code == 422, r.text


def test_join_protocole(observateur, administrateur, protocoles_base):
    macro_protocole = protocoles_base[0]
    protocole = protocoles_base[1]
    # Join a protocole
    etag = observateur.user['_etag']
    r = observateur.patch(observateur.url, headers={'If-Match': etag},
                          json={'protocoles': {str(protocole['_id']): {}}})
    assert r.status_code == 200, r.text
    observateur.update_user()
    etag = observateur.user['_etag']
    # Try to join dummy protocoles
    for protocole_id in [
            'dummy',
            observateur.user_id,
            "549b444b13adf218427fb681"]:
        r = observateur.patch(observateur.url, headers={'If-Match': etag},
                              json={'protocoles': {protocole_id: {}}})
        assert r.status_code == 422, protocole_id
    # Try to validate myself
    r = observateur.patch(observateur.url,
                          headers={'If-Match': etag},
                          json={'protocoles': {str(protocole['_id']): {'valide': True}}})
    assert r.status_code == 422, r.text
    # Admin validates me
    r = administrateur.patch(observateur.url,
                             headers={'If-Match': etag},
                             json={'protocoles': {str(protocole['_id']): {'valide': True}}})
    assert r.status_code == 200, r.text
    observateur.update_user()
    assert observateur.user['protocoles'] == {
        str(protocole['_id']): {'valide': True}}
    # Macro-protocoles are not subscriptable
    etag = observateur.user['_etag']
    r = observateur.patch(observateur.url,
                          headers={'If-Match': etag},
                          json={'protocoles': {str(macro_protocole['_id']): {}}})
    assert r.status_code == 422, r.text
