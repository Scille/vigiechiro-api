import requests
from pymongo import MongoClient
import pytest

from common import db, administrateur, observateur, eve_post_internal
from test_taxon import taxons_base


@pytest.fixture
def protocoles_base(request, taxons_base):
    # Insert parent
    payload_macro = {
        'titre': 'Vigiechiro',
        'description': 'Procole parent vigiechiro',
        'macro_protocole': True,
        'tag': ['chiroptères'],
        'taxon': taxons_base[0]['_id'],
        'type_site': 'LINEAIRE',
        'algo_tirage_site': 'CARRE',
    }
    eve_post_internal('protocoles', payload_macro)
    id_macro = db.protocoles.find_one({'titre': payload_macro['titre']})['_id']
    payload_sub = {
        'titre': 'Vigiechiro-A',
        'description': 'Procole enfant vigiechiro',
        'tag': ['chiroptères'],
        'taxon': taxons_base[0]['_id'],
        'type_site': 'LINEAIRE',
        'algo_tirage_site': 'CARRE',
        'parent': id_macro,
        'configuration_participation': ['micro0_hauteur', 'micro0_position']
    }
    eve_post_internal('protocoles', payload_sub)
    payload_sub = {
        'titre': 'Vigieortho',
        'description': 'Procole vigieortho',
        'tag': ['orthoptères'],
        'taxon': taxons_base[0]['_id'],
        'type_site': 'LINEAIRE',
        'algo_tirage_site': 'CARRE',
    }
    eve_post_internal('protocoles', payload_sub)

    def finalizer():
        db.protocoles.remove()
    request.addfinalizer(finalizer)
    return db.protocoles.find()


@pytest.fixture
def new_protocole_payload(request, taxons_base):
    payload = {
        'titre': 'Vigiechiro-Z',
        'type_site': 'POLYGONE',
        'algo_tirage_site': 'ROUTIER',
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
                          json={'tag': ['new_tag']})
    assert r.status_code == 403, r.text
    r = observateur.put(url, headers={'If-Match': etag},
                        json=new_protocole_payload)
    assert r.status_code == 403, r.text
    r = observateur.delete(url, headers={'If-Match': etag})
    assert r.status_code == 403, r.text


def test_required_taxon(new_protocole_payload, administrateur):
    del new_protocole_payload['taxon']
    r = administrateur.post('/protocoles', json=new_protocole_payload)
    assert r.status_code == 422, r.text


def test_macro_protocoles(
        protocoles_base,
        new_protocole_payload,
        administrateur):
    new_protocole_payload['parent'] = str(protocoles_base[0]['_id'])
    r = administrateur.post('/protocoles', json=new_protocole_payload)
    assert r.status_code == 201, r.text
    url = '/protocoles/' + r.json()['_id']
    etag = r.json()['_etag']
    for dummy_id in [
            'dummy',
            '5490237a1d41c81800d52c18',
            administrateur.user_id]:
        r = administrateur.patch(url, headers={'If-Match': etag},
                                 json={'parent': dummy_id})
        assert r.status_code == 422, r.text


def test_participation_configuration(
        protocoles_base,
        new_protocole_payload,
        administrateur):
    # Try to set dummy configuration
    new_protocole_payload['configuration_participation'] = ['dummy']
    r = administrateur.post('/protocoles', json=new_protocole_payload)
    assert r.status_code == 422, r.text
    # Same thing but with put/patch
    url = '/protocoles/' + str(protocoles_base[0]['_id'])
    etag = protocoles_base[0]['_etag']
    r = administrateur.put(
        url,
        headers={
            'If-Match': etag},
        json=new_protocole_payload)
    assert r.status_code == 422, r.text
    payload = {'configuration_participation': ['dummy']}
    r = administrateur.patch(url, headers={'If-Match': etag}, json=payload)
    assert r.status_code == 422, r.text
