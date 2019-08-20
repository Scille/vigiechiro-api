import requests
from pymongo import MongoClient
from unittest.mock import ANY
import pytest

from .common import db, administrateur, observateur, with_flask_context
from .test_taxons import taxons_base

from vigiechiro.resources import protocoles as protocoles_resource


@pytest.fixture
def protocole_point_fixe(request, administrateur, taxons_base):
    protocole_titre = 'Test'
    payload = {
        'titre': protocole_titre,
        'type_site': 'POINT_FIXE',
        'taxon': str(taxons_base[0]['_id'])
    }
    r = administrateur.post('/protocoles', json=payload)
    assert r.status_code == 201, r.text
    return r.json(), taxons_base[0]


@pytest.fixture
def protocoles_base(request, taxons_base):
    # Insert macro protocole first
    macro_protocole = {
        'titre': 'Vigiechiro',
        'description': 'Procole parent vigiechiro',
        'macro_protocole': True,
        'tags': ['chiroptères'],
        'taxon': taxons_base[0]['_id'],
    }
    @with_flask_context
    def insert_macro_protocole():
        inserted = protocoles_resource.insert(macro_protocole, auto_abort=False)
        assert inserted
        return inserted
    macro_protocole = insert_macro_protocole()
    # Then regular protocoles
    regular_protocoles = [
        {
            'titre': 'Vigiechiro-A',
            'description': 'Procole enfant vigiechiro',
            'tags': ['chiroptères'],
            'taxon': taxons_base[0]['_id'],
            'type_site': 'ROUTIER',
            'parent': macro_protocole['_id'],
            'configuration_participation': ['micro0_hauteur', 'micro0_position']
        },
        {
            'titre': 'Vigieortho',
            'description': 'Procole vigieortho',
            'tags': ['orthoptères'],
            'taxon': taxons_base[0]['_id'],
            'type_site': 'ROUTIER'
        }
    ]
    @with_flask_context
    def insert_regular_protocoles():
        inserted_protocoles = []
        for protocole in regular_protocoles:
            inserted_protocole = protocoles_resource.insert(protocole, auto_abort=False)
            assert inserted_protocole
            inserted_protocoles.append(inserted_protocole)
        return inserted_protocoles
    regular_protocoles = insert_regular_protocoles()
    protocoles = [macro_protocole] + regular_protocoles
    def finalizer():
        for protocole in protocoles:
            db.protocoles.remove()
    request.addfinalizer(finalizer)
    return protocoles


@pytest.fixture
def new_protocole_payload(request, taxons_base):
    payload = {
        'titre': 'Vigiechiro-Z',
        'type_site': 'ROUTIER',
        'taxon': str(taxons_base[0]['_id'])
    }

    def finalizer():
        db.protocoles.remove()
    request.addfinalizer(finalizer)
    return payload


def test_access(protocoles_base, new_protocole_payload, observateur):
    r = observateur.get('/protocoles')
    assert r.status_code == 200, r.text
    assert len(r.json()['_items']) == 3
    # User cannot modify or create protocoles
    r = observateur.post('/protocoles', json=new_protocole_payload)
    assert r.status_code == 403, r.text
    url = '/protocoles/' + str(protocoles_base[0]['_id'])
    etag = protocoles_base[0]['_etag']
    r = observateur.patch(url, headers={'If-Match': etag},
                          json={'tags': ['new_tag']})
    assert r.status_code == 403, r.text


def test_required_taxon(new_protocole_payload, administrateur):
    del new_protocole_payload['taxon']
    r = administrateur.post('/protocoles', json=new_protocole_payload)
    assert r.status_code == 422, r.text


def test_macro_protocoles(protocoles_base, new_protocole_payload, administrateur):
    new_protocole_payload['parent'] = str(protocoles_base[0]['_id'])
    r = administrateur.post('/protocoles', json=new_protocole_payload)
    assert r.status_code == 201, r.text
    print(r.json())
    url = '/protocoles/' + r.json()['_id']
    etag = r.json()['_etag']
    for dummy_id in ['dummy', '5490237a1d41c81800d52c18', administrateur.user_id]:
        r = administrateur.patch(url, headers={'If-Match': etag},
                                 json={'parent': dummy_id})
        assert r.status_code in [422, 404], r.text


def test_participation_configuration(protocoles_base, new_protocole_payload,
                                     administrateur):
    # Try to set dummy configuration
    new_protocole_payload['configuration_participation'] = ['dummy']
    r = administrateur.post('/protocoles', json=new_protocole_payload)
    assert r.status_code == 422, r.text
    # Same thing but with put/patch
    url = '/protocoles/' + str(protocoles_base[0]['_id'])
    etag = protocoles_base[0]['_etag']
    payload = {'configuration_participation': ['dummy']}
    r = administrateur.patch(url, headers={'If-Match': etag}, json=payload)
    assert r.status_code == 422, r.text


def test_list_protocole_users(protocoles_base, observateur, administrateur):
    protocole = protocoles_base[1]
    protocole_id = str(protocole['_id'])
    another_protocole = protocoles_base[2]
    another_protocole_id = str(another_protocole['_id'])
    # Join a protocole
    r = observateur.put('/moi/protocoles/' + protocole_id)
    assert r.status_code == 200, r.text
    r = administrateur.put('/moi/protocoles/' + protocole_id)
    assert r.status_code == 200, r.text
    # Join another protocole
    r = observateur.put('/moi/protocoles/' + another_protocole_id)
    assert r.status_code == 200, r.text
    # Admin should be automatically validate while joining a protocole
    administrateur.update_user()
    for protocole in administrateur.user['protocoles']:
        assert protocole.get('valide', None) == True
    observateur.update_user()
    # Now try to get back the list of user registered to the protocole
    users_protocole_url = '/protocoles/{}/observateurs'.format(protocole_id)
    r = observateur.get(users_protocole_url)
    assert r.status_code == 200, r.text
    assert len(r.json()['_items']) == 2
    # Same thing with filter : TOUS
    r = observateur.get(users_protocole_url, params={'type': 'TOUS'})
    assert r.status_code == 200, r.text
    assert len(r.json()['_items']) == 2
    # VALIDES
    r = observateur.get(users_protocole_url, params={'type': 'VALIDES'})
    assert r.status_code == 200, r.text
    assert len(r.json()['_items']) == 1
    assert r.json()['_items'][0]['_id'] == administrateur.user_id
    # A_VALIDER
    r = observateur.get(users_protocole_url, params={'type': 'A_VALIDER'})
    assert r.status_code == 200, r.text
    assert len(r.json()['_items']) == 1
    assert r.json()['_items'][0]['_id'] == observateur.user_id


def test_autojoin_protocole(protocoles_base, observateur, administrateur):
    protocole = protocoles_base[1]
    protocole_id = str(protocole['_id'])
    another_protocole = protocoles_base[2]
    another_protocole_id = str(another_protocole['_id'])

    # Mark protocoles as autojoin
    r = administrateur.patch(
        '/protocoles/' + protocole_id,
        headers={'If-Match': protocole['_etag']},
        json={'autojoin': True}
    )
    assert r.status_code == 200, r.text
    r = administrateur.patch(
        '/protocoles/' + another_protocole_id,
        headers={'If-Match': another_protocole['_etag']},
        json={'autojoin': True}
    )
    assert r.status_code == 200, r.text

    # Observateur accept charte, autojoin should kicks in
    r = observateur.patch('/moi', json={'charte_acceptee': True})
    assert r.status_code == 200, r.text

    observateur.update_user()
    assert observateur.user['charte_acceptee'] is True
    assert observateur.user['protocoles'] == [
        {
            'date_inscription': ANY,
            'protocole': protocole['_id'],
            'valide': True
        },
        {
            'date_inscription': ANY,
            'protocole': another_protocole['_id'],
            'valide': True
        }
    ]
