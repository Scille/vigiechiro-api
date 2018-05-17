import requests
import pytest
import base64
import json
from bson import ObjectId
from datetime import datetime, timedelta

from .common import db, observateur, validateur, administrateur, format_datetime, with_flask_context
from .test_protocoles import protocoles_base
from .test_taxons import taxons_base
from vigiechiro import settings
from vigiechiro.resources import utilisateurs as utilisateurs_resource


@pytest.fixture(scope="module")
def users_base(request):
    token_expire = datetime.utcnow() + timedelta(days=1)
    users = [
      {'nom': 'Doe',
       'prenom': 'John',
       'pseudo': 'n00b',
       'telephone': '01 23 45 67 89',
       'donnees_publiques': False,
       'charte_acceptee': False,
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
         'charte_acceptee': True,
         'tags': ['Python', 'BDFL'],
         'organisation': 'Python fundation',
         'role': 'Administrateur',
         'tokens': {'IP12XQN81X4AX3NYP9TIRDUVDJS4KJXE': token_expire}}
    ]
    @with_flask_context
    def insert_users():
        inserted_users = []
        for user in users:
            inserted_user = utilisateurs_resource.insert(user, auto_abort=False,
                additional_context={'internal': True})
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
        r = administrateur.patch('/moi', json={'role': dummy_role})
        assert r.status_code == 422, r.text


def test_user_route(observateur):
    r = observateur.get('/moi')
    assert r.status_code == 200, r.text
    content = r.json()
    for key in ['nom', 'email']:
        assert observateur.user[key] == content[key], content
    r = observateur.patch('/moi', json={'commentaire': 'New comment'})
    assert r.status_code == 200, r.text
    observateur.update_user()
    assert observateur.user['commentaire'] == 'New comment'


def test_donnee_publiques_only_for_admin(observateur, administrateur):
    # Cannot change this field by myself...
    payload = {'donnees_publiques': True}
    r = observateur.patch('/moi', json=payload)
    assert r.status_code == 422, r.text
    # ...but admin can !
    r = administrateur.patch(observateur.url, json=payload)
    assert r.status_code == 200, r.text
    observateur.update_user()
    assert observateur.user['donnees_publiques']


def test_rights_write(observateur, administrateur):
    # Change data for myself is allowed...
    payload = {'charte_acceptee': True}
    r = observateur.patch('/moi', json=payload)
    assert r.status_code == 200, r.text
    observateur.update_user()
    assert observateur.user['charte_acceptee']
    # ...but I can't change for others !
    r = observateur.patch(administrateur.url, json=payload)
    assert r.status_code == 403, r.text
    # Same thing, cannot change my own rights
    r = observateur.patch(observateur.url, json={'role': 'Administrateur'})
    assert r.status_code == 403, r.text
    # Of courses, admin can
    r = administrateur.patch(observateur.url, json={'role': 'Validateur'})
    assert r.status_code == 200, r.text
    observateur.update_user()
    assert observateur.user['role'] == 'Validateur'
    # Finally, try to change various allowed stuffs
    for payload in [{'pseudo': 'my new pseudo !'},
                    {'email': 'new@email.com'},
                    {'nom': 'newLastName', 'prenom': 'newFirstName'}]:
        r = observateur.patch('/moi', json=payload)
        assert r.status_code == 200, r.text


def test_rights_read(observateur, validateur):
    # Observateur has limited view on others user's profile
    r = observateur.get('/utilisateurs')
    assert r.status_code == 200, r.text
    for item in r.json()['_items']:
        # if item['_id'] == observateur.user_id:
        #     continue
        assert 'email' not in item
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
    assert 'tokens' not in r.json()
    # Of course, observateur has full access of it own profile
    r = observateur.get('/moi')
    assert r.status_code == 200, r.text
    assert 'email' in r.json()


def test_readonly_fields(observateur, administrateur):
    payload = {'role': 'Administrateur'}
    r = observateur.patch('/moi', json=payload)
    assert r.status_code == 422, r.text
    r = observateur.patch(administrateur.url, json=payload)
    assert r.status_code == 403, r.text
    # Admin can do everything !
    r = administrateur.patch(observateur.url, json=payload)
    administrateur.update_user()
    assert r.status_code == 200, r.text
    # Try to change for itself
    r = administrateur.patch('/moi', json=payload)
    administrateur.update_user()
    assert r.status_code == 200, r.text


def test_internal_resource(observateur):
    # Try to post internal resources
    payloads = [{"tokens": {"26GLD0MWB2ISABOQN2F5K1JNKVZNLOOT": "2025-01-18T13:07:03.051Z"}},
                {'github_id': '1872655'},
                {'facebook_id': '1872655'},
                {'google_id': '1872655'}]
    for payload in payloads:
        r = observateur.patch('/moi', json=payload)
        assert r.status_code == 422, r.text
    # Also make sure we can't access internal resources
    internal_data = {'github_id': '1872655', 'facebook_id': '1872656',
                     'google_id': '1872657'}
    db.utilisateurs.update({'_id': ObjectId(observateur.user_id)},
                           {'$set': internal_data})
    r = observateur.get('/moi')
    assert r.status_code == 200, r.text
    user_data = r.json()
    assert 'tokens' not in user_data
    for key in internal_data.keys():
        assert key not in user_data


def test_join_protocole(observateur, administrateur, protocoles_base):
    macro_protocole = protocoles_base[0]
    macro_protocole_id = str(macro_protocole['_id'])
    protocole = protocoles_base[1]
    protocole_id = str(protocole['_id'])
    protocole_url = '/moi/protocoles/{}'
    # Try to join dummy protocoles
    for bad_protocole_id in ['dummy', observateur.user_id,
                             '549b444b13adf218427fb681']:
        r = observateur.put(protocole_url.format(bad_protocole_id))
        assert r.status_code in [404, 405, 422], r.text
    # Try to manualy add a protocole to myself
    r = observateur.patch('/moi',
                          json={'protocoles': [{'protocole': protocole_id}]})
    assert r.status_code == 422, r.text
    # Join a protocole
    r = observateur.put(protocole_url.format(protocole_id))
    assert r.status_code == 200, r.text
    # Get back user profile and check protocoles expended field
    r = observateur.get('/moi')
    assert r.status_code == 200, r.text
    protocoles = r.json()['protocoles']
    assert len(protocoles) == 1, protocoles
    assert 'date_inscription' in protocoles[0], protocoles[0]
    protocole_expended = protocoles[0].get('protocole', '')
    # Make sure the protocole is an expended resource
    assert isinstance(protocole_expended, dict)
    assert protocole_expended.get('_id', None) == protocole_id
    assert protocole_expended.get('titre', None) == protocole['titre']
    # Try to validate myself
    validate_url = '/protocoles/{}/observateurs/{}'.format(
        protocole_id, observateur.user_id)
    r = observateur.put(validate_url)
    assert r.status_code == 403, r.text
    # Admin validates me
    r = administrateur.put(validate_url)
    assert r.status_code == 200, r.text
    observateur.update_user()
    assert observateur.user['protocoles'][0]['valide']
    # Admin can reject also reject me
    r = administrateur.delete(validate_url)
    assert r.status_code == 200, r.text
    observateur.update_user()
    assert observateur.user.get('protocoles', []) == []
    # Macro-protocoles are not subscriptable
    r = observateur.put(protocole_url.format(macro_protocole_id))
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
    # import pdb; pdb.set_trace()
    macro_protocole = protocoles_base[0]
    protocole1_id = str(protocoles_base[1]['_id'])
    protocole1_titre = protocoles_base[1]['titre']
    protocole2_id = str(protocoles_base[2]['_id'])
    protocole2_titre = protocoles_base[2]['titre']
    protocole_url = '/moi/protocoles/{}'
    # Make the observateur join a protocole and validate it
    r = observateur.put(protocole_url.format(protocole1_id))
    assert r.status_code == 200, r.text
    r = administrateur.put('/protocoles/{}/observateurs/{}'.format(
        protocole1_id, observateur.user_id))
    assert r.status_code == 200, r.text
    observateur.update_user()
    # Now observateur join another protocole, must not interfere with the other
    r = observateur.put(protocole_url.format(protocole2_id))
    assert r.status_code == 200, r.text
    r = observateur.get('/moi')
    assert r.status_code == 200, r.text
    protocoles = r.json()['protocoles']
    assert len(protocoles) == 2
    # Make sure the given protocoles are expended
    protocole1 = protocoles[0]
    protocole1_expended = protocoles[0]['protocole']
    protocole2 = protocoles[1]
    protocole2_expended = protocoles[1]['protocole']
    print(protocole1_expended)
    assert isinstance(protocole1_expended, dict)
    assert protocole1_expended.get('_id', None) == protocole1_id
    assert protocole1_expended.get('titre', None) == protocole1_titre
    assert protocole1.get('valide', False) == True
    assert isinstance(protocole2_expended, dict)
    assert protocole2_expended.get('_id', None) == protocole2_id
    assert protocole2_expended.get('titre', None) == protocole2_titre
    assert protocole2.get('valide', False) == False
    # List observateur's protocoles
    r = observateur.get('/moi/protocoles')
    assert r.status_code == 200, r.text
    assert len(r.json()['_items']) == 2, r.json()
