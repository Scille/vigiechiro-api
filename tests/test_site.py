import requests
from pymongo import MongoClient
import pytest
from bson import ObjectId

from common import db, administrateur, observateur, eve_post_internal
from test_protocole import protocoles_base
from test_taxon import taxons_base


@pytest.fixture
def obs_sites_base(request, protocoles_base, observateur, administrateur):
    # Register the observateur to a protocole
    protocole_id = str(protocoles_base[1]['_id'])
    etag = observateur.user['_etag']
    r = administrateur.patch(observateur.url,
                             headers={'If-Match': etag},
                             json={'protocoles': [{'protocole': protocole_id,
                                                   'valide': True}]})
    observateur.update_user()
    assert r.status_code == 200, r.text
    # Create sites for the observateur
    site1_payload = {
        'protocole': protocole_id,
        'observateur': str(observateur.user_id),
        'commentaire': 'My little site'
    }
    r = observateur.post('/sites', json=site1_payload)
    assert r.status_code == 201, r.text
    site2_payload = {
        'protocole': protocole_id,
        'observateur': observateur.user_id,
        'commentaire': 'Another site'
    }
    r = observateur.post('/sites', json=site1_payload)
    assert r.status_code == 201, r.text
    site2_payload = {
        'protocole': protocole_id,
        'observateur': observateur.user_id,
        'commentaire': 'Another site'
    }
    r = observateur.post('/sites', json=site2_payload)
    assert r.status_code == 201, r.text
    def finalizer():
        db.sites.remove()
    request.addfinalizer(finalizer)
    observateur_id = ObjectId(observateur.user_id)
    return (observateur,
        db.sites.find({'observateur': observateur_id}).sort([('_id', 1)]))


@pytest.fixture
def new_site_payload(request, protocoles_base):
    payload = {
        'protocole': str(protocoles_base[0]['_id']),
        'commentaire': 'new_site'
    }
    def finalizer():
        db.sites.remove()
    request.addfinalizer(finalizer)
    return payload


def test_non_register_create_site(protocoles_base, observateur, administrateur):
    # Cannot create site if not register to a protocole
    site_payload = {
        'protocole': str(protocoles_base[1]['_id']),
        'commentaire': 'My little site'
    }
    r = observateur.post('/sites', json=site_payload)
    assert r.status_code == 422, r.text
    # Even admin can do that, IMPOSSIBRU !
    r = administrateur.post('/sites', json=site_payload)
    assert r.status_code == 422, r.text


def test_create_site_non_valide(observateur, protocoles_base):
    # Register the observateur to a protocole, but doesn't validate it
    protocole_id = str(protocoles_base[1]['_id'])
    r = observateur.post('/protocoles/{}/action/join'.format(protocole_id))
    assert r.status_code == 200, r.text
    # Observateur is allowed to create multiple sites
    site_payload = {
        'protocole': protocole_id,
        'commentaire': 'My little site'
    }
    for _ in range(3):
        r = observateur.post('/sites', json=site_payload)
        assert r.status_code == 201, r.text


def test_create_site(administrateur, observateur, protocoles_base):
    # Register the observateur to a protocole
    protocole_id = str(protocoles_base[1]['_id'])
    etag = observateur.user['_etag']
    r = administrateur.patch(observateur.url,
                             headers={'If-Match': etag},
                             json={'protocoles': [{'protocole': protocole_id,
                                                   'valide': True}]})
    assert r.status_code == 200, r.text
    # Create site for the observateur
    site_payload = {
        'protocole': protocole_id,
        'commentaire': 'My little site'
    }
    r = observateur.post('/sites', json=site_payload)
    assert r.status_code == 201, r.text
    r = observateur.get('/sites/' + r.json()['_id'])
    assert r.status_code == 200, r.text
    # Implicitly set the observateur in the created site
    assert r.json()['observateur'] == observateur.user_id


def test_create_site_explicit_obs(administrateur, observateur, protocoles_base):
    # Register the observateur to a protocole
    protocole_id = str(protocoles_base[1]['_id'])
    etag = observateur.user['_etag']
    r = administrateur.patch(observateur.url,
                             headers={'If-Match': etag},
                             json={'protocoles': [{'protocole': protocole_id,
                                                   'valide': True}]})
    assert r.status_code == 200, r.text
    # Create a site, but specify another observateur than the poster !
    site_payload = {
        'protocole': str(protocoles_base[1]['_id']),
        'observateur': administrateur.user_id,
        'commentaire': 'My little site'
    }
    r = observateur.post('/sites', json=site_payload)
    assert r.status_code == 422, r.text
    # Admin is the only allowed to do that
    site_payload['observateur'] = observateur.user_id
    r = administrateur.post('/sites', json=site_payload)
    assert r.status_code == 201, r.text
    r = observateur.get('/sites/' + r.json()['_id'])
    assert r.status_code == 200, r.text
    assert r.json()['observateur'] == observateur.user_id


def test_modify_fields(protocoles_base, obs_sites_base, administrateur):
    observateur, sites_base = obs_sites_base
    print(sites_base)
    url = 'sites/' + str(sites_base[0]['_id'])
    etag = sites_base[0]['_etag']
    protocole = str(protocoles_base[0]['_id'])
    # Try to modify read-only fields
    r = observateur.patch(url, headers={'If-Match': etag},
                          json={'protocole': protocole})
    assert r.status_code == 422, r.text
    # Admin can of course
    r = administrateur.patch(url, headers={'If-Match': etag},
                             json={'protocole': protocole})
    assert r.status_code == 200, r.text
    etag = r.json()['_etag']
    # Same for observateur field
    r = observateur.patch(url, headers={'If-Match': etag},
                          json={'observateur': observateur.user_id})
    assert r.status_code == 422, r.text
    # Admin can of course
    r = administrateur.patch(url, headers={'If-Match': etag},
                             json={'observateur': observateur.user_id})
    assert r.status_code == 200, r.text


def test_lock_site(administrateur, obs_sites_base):
    # Make sure the observateur cannot lock it own site
    observateur, sites_base = obs_sites_base
    url = 'sites/' + str(sites_base[0]['_id'])
    etag = sites_base[0]['_etag']
    #  Observateur cannot lock site
    r = observateur.patch(url, headers={'If-Match': etag},
                          json={'verrouille': True})
    assert r.status_code == 422, r.text
    #  And admin can of course
    r = administrateur.patch(url, headers={'If-Match': etag},
                             json={'verrouille': True})
    assert r.status_code == 200, r.text
    r = observateur.get(url)
    assert r.status_code == 200, r.text
    assert 'verrouille' in r.json() and r.json()['verrouille']
    # Now observateur cannot modify the site
    etag = r.json()['_etag']
    r = observateur.patch(url, headers={'If-Match': etag},
                          json={'commentaire': "I can't do that"})
    assert r.status_code == 422, r.text


@pytest.mark.xfail
def test_increment_numero(administrateur, new_site_payload):
    bad_payload = new_site_payload.copy()
    # Cannot specify site number on post
    bad_payload['numero'] = 1
    r = administrateur.post('/sites', json=bad_payload)
    assert r.status_code == 422, r.text
    # Regular site posts
    r = administrateur.post('/sites', json=new_site_payload)
    assert r.status_code == 201, r.text
    url = r.json()['_links']['self']['href']
    r = administrateur.get(url)
    assert 'numero' in r.json()
    r = administrateur.post('/sites', json=new_site_payload)
    assert r.status_code == 201, r.text


def test_get_stoc(observateur):
    r = observateur.get('/sites/stoc')
    assert r.status_code == 200, r.text


def test_create_site_bad_payload(administrateur, observateur, protocoles_base):
    # Register the observateur to a protocole
    protocole_id = str(protocoles_base[1]['_id'])
    etag = observateur.user['_etag']
    r = administrateur.patch(observateur.url,
                             headers={'If-Match': etag},
                             json={'protocoles': [{'protocole': protocole_id,
                                                   'valide': True}]})
    assert r.status_code == 200, r.text
    # Site payload's geojson doesn't match expected geojson schema
    site_payload = {
        "protocole": protocole_id,
        "localites": [
            {"type":"Point", "coordinates":[48.862004474432936,2.338886260986328]},
            {"type":"Point", "coordinates":[48.877812415009195,2.3639488220214844]},
            {"type":"LineString", "coordinates":[
                [48.86539231071163,2.353992462158203],
                [48.87239311228893,2.353649139404297],
                [48.87736082887189,2.344379425048828]]
            }
        ]
    }
    r = observateur.post('/sites', json=site_payload)
    assert r.status_code == 422, r.text
