import requests
import pytest
import base64
import json
from bson import ObjectId
from datetime import datetime, timedelta

from common import db, observateur, validateur, administrateur, eve_post_internal, format_datetime
from vigiechiro import settings
from test_protocole import protocoles_base
from test_taxon import taxons_base


@pytest.fixture(scope="module")
def users_base(request):
    token_expire = datetime.utcnow() + timedelta(days=1)
    user1 = {'nom': 'Doe',
             'prenom': 'John',
             'pseudo': 'n00b',
             'telephone': '01 23 45 67 89',
             'donnees_publiques': False,
             'email': 'john.doe@gmail.com',
             'role': 'Observateur',
             'tokens': {'WPKQHC7LLNSI5KJAFEYXTD89W61RSDBO': token_expire,
                        '6Z2GN5MJ8P1B234SP5RVJJTO2A2NOLF0': token_expire}}
    eve_post_internal('utilisateurs', user1)
    user2 = {'nom': 'van rossum',
             'prenom': 'guido',
             'pseudo': 'gr0k',
             'email': 'guido@python.org',
             'donnees_publiques': True,
             'tags': ['Python', 'BDFL'],
             'organisation': 'Python fundation',
             'role': 'Administrateur',
             'tokens': {'IP12XQN81X4AX3NYP9TIRDUVDJS4KJXE': token_expire}}
    eve_post_internal('utilisateurs', user2)
    def finalizer():
        db.utilisateurs.remove()
    request.addfinalizer(finalizer)
    return db.utilisateurs.find().sort([('_id', 1)])


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
    # Try to post internal resources
    payloads = [{'tokens': ['7U5L5J8B7BEDH5MFOHZ8D2834AUNTPXI']},
                {'github_id': '1872655'},
                {'facebook_id': '1872655'},
                {'google_id': '1872655'}]
    for payload in payloads:
        r = observateur.patch(observateur.url,
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
    protocole_url = '/protocoles/{}/action/join'
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
    assert observateur.user['protocoles'] == [{'protocole': protocole_id}]
    # Try to validate myself
    etag = observateur.user['_etag']
    r = observateur.patch(observateur.url, headers={'If-Match': etag},
                          json={'protocoles': [{'protocole': protocole_id,
                                                'valide': True}]})
    assert r.status_code == 422, r.text
    # Admin validates me
    date_inscription = format_datetime(datetime.utcnow())
    r = administrateur.patch(observateur.url, headers={'If-Match': etag},
                             json={'protocoles': [{'protocole': protocole_id,
                                                   'date_inscription': date_inscription,
                                                   'valide': True}]})
    assert r.status_code == 200, r.text
    observateur.update_user()
    assert observateur.user['protocoles'] == [{'protocole': protocole_id,
                                               'date_inscription': date_inscription,
                                               'valide': True}]
    # Macro-protocoles are not subscriptable
    etag = observateur.user['_etag']
    r = observateur.post(protocole_url.format(macro_protocole_id))
    assert r.status_code == 422, r.text


def test_multi_join(observateur, administrateur, protocoles_base):
    macro_protocole = protocoles_base[0]
    protocole1_id = str(protocoles_base[1]['_id'])
    protocole2_id = str(protocoles_base[2]['_id'])
    protocole_url = '/protocoles/{}/action/join'
    # Make the observateur join a protocole and validate it
    etag = observateur.user['_etag']
    date_inscription = format_datetime(datetime.utcnow())
    r = administrateur.patch(observateur.url, headers={'If-Match': etag},
                             json={'protocoles': [{'protocole': protocole1_id,
                                                   'date_inscription': date_inscription,
                                                   'valide': True}]})
    assert r.status_code == 200, r.text
    observateur.update_user()
    # Now observateur join another protocole, must not interfere with the other
    r = observateur.post(protocole_url.format(protocole2_id))
    assert r.status_code == 200, r.text
    observateur.update_user()
    assert observateur.user['protocoles'] == [{'protocole': protocole1_id,
                                               'date_inscription': date_inscription,
                                               'valide': True},
                                              {'protocole': protocole2_id}]
