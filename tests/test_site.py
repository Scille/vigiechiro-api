import requests
from pymongo import MongoClient
import pytest

from common import db, administrateur, observateur, eve_post_internal
from test_protocole import protocoles_base
from test_taxon import taxons_base


@pytest.fixture
def sites_base(request, protocoles_base):
    site1_payload = {
        'protocole': protocoles_base[0]['_id'],
        'commentaire': 'My little site',
    }
    eve_post_internal('sites', site1_payload)

    def finalizer():
        db.sites.remove()
    request.addfinalizer(finalizer)
    return db.sites.find()


@pytest.fixture
def new_site_payload(request, protocoles_base):
    payload = {
        'protocole': str(protocoles_base[0]['_id']),
        'commentaire': 'new_site'
    }

    def finalizer():
        db.sites.remove({'commentaire': payload['commentaire']})
    request.addfinalizer(finalizer)
    return payload


# TODO add connexion with participation :
#  - observateur linked with participation/site
#  - observateur can modfiy it own site
#  - another observateur is not allowed to modify this site
#  - administrateur lock the site
#  - observateur is no longer allowed to modify the site
def test_verrouille(sites_base, observateur, administrateur):
    url = 'sites/'+str(sites_base[0]['_id'])
    etag = sites_base[0]['_etag']
    #  Observateur cannot lock site
    r = observateur.patch(url, headers={'If-Match': etag},
                          json={'verrouille': True})
    assert r.status_code == 401, r.text
    #  And admin can of course
    r = administrateur.patch(url, headers={'If-Match': etag},
                             json={'verrouille': True})
    assert r.status_code == 200, r.text
    r = observateur.get(url)
    assert r.status_code == 200, r.text
    assert 'verrouille' in r.json() and r.json()['verrouille'] == True
    # Now observateur cannot modify the site
    r = observateur.patch(url, headers={'If-Match': etag},
                          json={'commentaire': "I can't do that"})
    assert r.status_code == 401, r.text


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
