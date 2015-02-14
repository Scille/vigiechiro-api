import requests
import pytest
import base64
import json
from bson import ObjectId
from datetime import datetime, timedelta

from common import db, observateur, validateur, administrateur, format_datetime, with_flask_context
from vigiechiro import settings
from vigiechiro.resources import utilisateurs as utilisateurs_resource
from test_protocoles import protocoles_base
from test_taxons import taxons_base


@pytest.fixture(scope="module")
def users_base(request):
    token_expire = datetime.utcnow() + timedelta(days=1)
    users = [
      {'nom': 'Doe',
       'prenom': 'John',
       'pseudo': 'n00b',
       'telephone': '01 23 45 67 89',
       'donnees_publiques': False,
       'email': 'john.doe@gmail.com',
       'email_public': 'john.doe.public@gmail.com',
       'role': 'Observateur',
       'tokens': {'WPKQHC7LLNSI5KJAFEYXTD89W61RSDBO': token_expire,
                  '6Z2GN5MJ8P1B234SP5RVJJTO2A2NOLF0': token_expire}},
        {'nom': 'van rossum',
         'prenom': 'guido',
         'pseudo': 'gr0k',
         'email': 'guido@python.org',
         'donnees_publiques': True,
         'tags': ['Python', 'BDFL'],
         'organisation': 'Python fundation',
         'role': 'Administrateur',
         'tokens': {'IP12XQN81X4AX3NYP9TIRDUVDJS4KJXE': token_expire}}
    ]
    @with_flask_context
    def insert_users():
        inserted_users = []
        for user in users:
            inserted_user = utilisateurs_resource.insert(user, auto_abort=False)
            assert inserted_user
            inserted_users.append(inserted_user)
        return inserted_users
    users = insert_users()
    def finalizer():
        for user in users:
            db.utilisateurs.remove({'_id': user['_id']})
    request.addfinalizer(finalizer)
    return users


def test_dummy_user(administrateur):
    for dummy in ['549982ae13adf2435290074b', 'dummy', '01234', ' ', '/']:
        r = administrateur.get('/utilisateurs/' + dummy)
        assert r.status_code in [404, 422], r.text


def test_dummy_role(administrateur):
    for dummy_role in ['Administrateur ', ' ', 'observateur']:
        r = administrateur.patch('/moi',
                                 headers={'If-Match': administrateur.user['_etag']},
                                 json={'role': dummy_role})
        assert r.status_code == 422, r.text


def test_user_route(observateur):
    r = observateur.get('/moi')
    assert r.status_code == 200, r.text
    content = r.json()
    for key in ['nom', 'email']:
        assert observateur.user[key] == content[key]
    r = observateur.patch('/moi',
                          headers={'If-Match': content['_etag']},
                          json={'commentaire': 'New comment'})
    assert r.status_code == 200, r.text
    observateur.update_user()
    assert observateur.user['commentaire'] == 'New comment'


def test_rights_write(observateur, administrateur):
    # Change data for myself is allowed...
    payload = {'donnees_publiques': True}
    r = observateur.patch('/moi',
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
    r = observateur.patch('/utilisateurs/{}'.format(observateur.user_id),
                          headers={'If-Match': observateur.user['_etag']},
                          json={'role': 'Administrateur'})
    assert r.status_code == 403, r.text
    # Of courses, admin can
    r = administrateur.patch('/utilisateurs/{}'.format(observateur.user_id),
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
        r = observateur.patch('/moi', headers={'If-Match': etag}, json=payload)
        assert r.status_code == 200, r.text
        etag = r.json()['_etag']


def test_rigths_read(observateur, validateur):
    # Observateur has limited view on others user's profile
    r = observateur.get('/utilisateurs')
    assert r.status_code == 200, r.text
    utilisateur = r.json()['_items'][0]
    assert 'email' not in utilisateur, utilisateur
    r = observateur.get(validateur.url)
    assert r.status_code == 200, r.text
    assert 'email' not in r.json()
    # Validateur and upper has full access on profiles
    r = validateur.get('/utilisateurs')
    assert r.status_code == 200, r.text
    utilisateur = r.json()['_items'][0]
    assert 'email' in utilisateur, utilisateur
    r = validateur.get(observateur.url)
    assert r.status_code == 200, r.text
    assert 'email' in r.json()
    # Of course, observateur has full access of it own profile
    r = observateur.get('/moi')
    assert r.status_code == 200, r.text
    assert 'email' in r.json()


def test_readonly_fields(observateur, administrateur):
    payloads = [{'role': 'Administrateur'}, {'protocoles': []}]
    for payload in payloads:
        r = observateur.patch('/moi',
                              headers={'If-Match': observateur.user['_etag']},
                              json=payload)
        assert r.status_code == 422, r.text
        # Admin can do everything !
        r = administrateur.patch(administrateur.url,
            headers={'If-Match': administrateur.user['_etag']}, json=payload)
        administrateur.update_user()
        assert r.status_code == 200, r.text


def test_internal_resource(observateur):
    # Try to post internal resources
    payloads = [{'tokens': ['7U5L5J8B7BEDH5MFOHZ8D2834AUNTPXI']},
                {'github_id': '1872655'},
                {'facebook_id': '1872655'},
                {'google_id': '1872655'}]
    for payload in payloads:
        r = observateur.patch('/moi',
                              headers={'If-Match': observateur.user['_etag']},
                              json=payload)
        assert r.status_code == 422, r.text
    # Also make sure we can't access internal resources
    internal_data = {'github_id': '1872655', 'facebook_id': '1872656',
                     'google_id': '1872657'}
    db.utilisateurs.update({'_id': ObjectId(observateur.user_id)},
                           {'$set': internal_data})
    r = observateur.get(observateur.url)
    assert r.status_code == 200, r.text
    for key in internal_data.keys():
        assert key not in r.json()


def test_join_protocole(observateur, administrateur, protocoles_base):
    macro_protocole = protocoles_base[0]
    macro_protocole_id = str(macro_protocole['_id'])
    protocole = protocoles_base[1]
    protocole_id = str(protocole['_id'])
    protocole_url = '/protocoles/{}/join'
    # Try to join dummy protocoles
    for bad_protocole_id in ['dummy', observateur.user_id,
                             '549b444b13adf218427fb681']:
        r = observateur.post(protocole_url.format(bad_protocole_id))
        assert r.status_code in [404, 422], r.text
    # Try to manualy add a protocole to myself
    etag = observateur.user['_etag']
    r = observateur.patch(observateur.url, headers={'If-Match': etag},
                          json={'protocoles': [{'protocole': protocole_id}]})
    # Join a protocole
    r = observateur.post(protocole_url.format(protocole_id))
    assert r.status_code == 200, r.text
    observateur.update_user()
    protocoles = observateur.user['protocoles']
    assert len(protocoles) == 1, protocoles
    assert 'date_inscription' in protocoles[0], protocoles[0]
    assert (protocoles[0].get('protocole', '') ==
            {'_id': protocole_id, 'titre': protocole['titre']}), protocoles[0]
    # Try to validate myself
    validate_url = '/protocoles/{}/observateurs/{}'.format(
        protocole_id, observateur.user_id)
    r = observateur.put(validate_url, json={'valide': True})
    assert r.status_code == 403, r.text
    # Admin validates me
    r = administrateur.put(validate_url, json={'valide': True})
    assert r.status_code == 200, r.text
    observateur.update_user()
    assert observateur.user['protocoles'][0]['valide']
    # Macro-protocoles are not subscriptable
    r = observateur.post(protocole_url.format(macro_protocole_id))
    assert r.status_code == 422, r.text


def validate_dict(scheme, to_validate):
    if isinstance(to_validate, list):
        for sub_validate in to_validate:
            validate_dict(scheme, sub_validate)
    # Look for unknown keys
    bad_keys = set(to_validate.keys()) - set(scheme.keys())
    assert not bad_keys, bad_keys
    required_keys = set()
    for key, value in scheme.items():
        if value.get('required', False):
            required_keys.add(key)
    missing_keys = required_keys - set(to_validate.keys())
    assert missing_keys, missing_keys
    for key, value in to_validate.items():
        if 'value' in scheme[key]:
            assert scheme[key]['value'] == value, key


def test_multi_join(observateur, administrateur, protocoles_base):
    macro_protocole = protocoles_base[0]
    protocole1_id = str(protocoles_base[1]['_id'])
    protocole1_titre = protocoles_base[1]['titre']
    protocole2_id = str(protocoles_base[2]['_id'])
    protocole2_titre = protocoles_base[2]['titre']
    protocole_url = '/protocoles/{}/join'
    # Make the observateur join a protocole and validate it
    r = observateur.post(protocole_url.format(protocole1_id))
    assert r.status_code == 200, r.text
    r = administrateur.put('/protocoles/{}/observateurs/{}'.format(
        protocole1_id, observateur.user_id), json={'valide': True})
    assert r.status_code == 200, r.text
    observateur.update_user()
    # Now observateur join another protocole, must not interfere with the other
    r = observateur.post(protocole_url.format(protocole2_id))
    assert r.status_code == 200, r.text
    observateur.update_user()
    assert len(observateur.user['protocoles']) == 2
    assert (observateur.user['protocoles'][0]['protocole'] ==
            {'_id': protocole1_id, 'titre': protocole1_titre})
    assert observateur.user['protocoles'][0]['valide'] == True
    assert (observateur.user['protocoles'][1]['protocole'] ==
            {'_id': protocole2_id, 'titre': protocole2_titre})
    assert observateur.user['protocoles'][1].get('valide', False) == False
    # List observateur's protocoles
    r = observateur.get('/moi/protocoles')
    assert r.status_code == 200, r.text
    assert len(r.json()['_items']) == 2, r.json()
