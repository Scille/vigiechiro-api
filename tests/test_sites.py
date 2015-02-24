import pytest
from bson import ObjectId
from datetime import datetime

from common import db, administrateur, observateur, format_datetime
from test_grille_stoc import grille_stoc
from test_protocoles import protocoles_base
from test_taxons import taxons_base


@pytest.fixture
def obs_sites_base(request, protocoles_base, observateur, administrateur):
    # Who knows why, cannot use grille_stoc as fixture...
    grilles = grille_stoc(request)
    protocole_id = str(protocoles_base[1]['_id'])
    # Register the observateur to a protocole
    r = observateur.put('/moi/protocoles/{}'.format(protocole_id))
    assert r.status_code == 200, r.text
    # Now validate the user
    r = administrateur.put('/protocoles/{}/observateurs/{}'.format(
        protocole_id, observateur.user_id), json={'valide': True})
    assert r.status_code == 200, r.text
    observateur.update_user()
    # Create sites for the observateur
    site1_payload = {
        'protocole': protocole_id,
        'grille_stoc': str(grilles[0]['_id']),
        'commentaire': 'My little site'
    }
    r = observateur.post('/sites', json=site1_payload)
    assert r.status_code == 201, r.text
    site2_payload = {
        'protocole': protocole_id,
        'grille_stoc': str(grilles[1]['_id']),
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


def test_list_own_sites(obs_sites_base):
    observateur, sites_base = obs_sites_base
    url = 'sites/{}'.format(sites_base[0]['_id'])
    r = observateur.get('/moi/sites')
    assert r.status_code == 200, r.text
    items = r.json()['_items']
    assert len(items) == 2, r.json()
    # Resource contains expended version of fields protocole and grille_stoc
    for item in items:
        for field in ['protocole', 'grille_stoc']:
            assert field in item
            assert isinstance(item[field], dict), item
            assert '_id' in item[field], item


@pytest.mark.xfail
def test_list_with_search(obs_sites_base):
    observateur, sites_base = obs_sites_base
    url = 'sites/{}'.format(sites_base[0]['_id'])
    r = observateur.get('/sites', params={'q': 'Chauve'})
    assert r.status_code == 200, r.text
    assert len(r.json()['_items']) == 1, r.json()
    assert r.json()['_items'][0]['libelle_long'] == 'Chauve-Souris'


def test_non_register_create_site(protocoles_base, observateur, administrateur):
    # Cannot create site if not register to a protocole
    site_payload = {
        'protocole': str(protocoles_base[1]['_id']),
        'commentaire': 'My little site'
    }
    r = observateur.post('/sites', json=site_payload)
    assert r.status_code == 422, r.text
    # Even admin can't do that, IMPOSSIBRU !
    r = administrateur.post('/sites', json=site_payload)
    assert r.status_code == 422, r.text


def test_create_site_non_valide(observateur, protocoles_base):
    # Register the observateur to a protocole, but doesn't validate it
    protocole_id = str(protocoles_base[1]['_id'])
    r = observateur.put('/moi/protocoles/{}'.format(protocole_id))
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
    r = observateur.put('/moi/protocoles/{}'.format(protocole_id))
    assert r.status_code == 200, r.text
    # Validate the user
    r = administrateur.put('/protocoles/{}/observateurs/{}'.format(
                           protocole_id, observateur.user_id))
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
    r = observateur.put('/moi/protocoles/{}'.format(protocole_id))
    assert r.status_code == 200, r.text
    # Validate the user
    r = administrateur.put('/protocoles/{}/observateurs/{}'.format(
                           protocole_id, observateur.user_id))
    assert r.status_code == 200, r.text
    # Create a new site for the observateur
    r = observateur.post('/sites', json={'protocole': protocole_id})
    assert r.status_code == 201, r.text
    site_url = '/sites/{}'.format(r.json()['_id'])
    # Observateur cannot give it site to someone else
    r = observateur.patch(site_url, json={'observateur': administrateur.user_id})
    assert r.status_code == 403, r.text
    # Admin is the only allowed to do that
    r = administrateur.patch(site_url, json={'observateur': administrateur.user_id})
    assert r.status_code == 200, r.text
    # Now observateur cannot use this site anymore
    # TODO : test participation
    r = observateur.post('{}/participations'.format(site_url),
                         json={'date_debut': format_datetime(datetime.utcnow())})
    assert r.status_code == 422, r.text


def test_lock_site(administrateur, obs_sites_base):
    # Make sure the observateur cannot lock it own site
    observateur, sites_base = obs_sites_base
    url = 'sites/{}'.format(sites_base[0]['_id'])
    #  Observateur cannot lock site
    r = observateur.patch(url, json={'verrouille': True})
    assert r.status_code == 403, r.text
    #  And admin can of course
    r = administrateur.patch(url, json={'verrouille': True})
    assert r.status_code == 200, r.text
    r = observateur.get(url)
    assert r.status_code == 200, r.text
    assert 'verrouille' in r.json() and r.json()['verrouille']
    # Now observateur cannot modify the site
    r = observateur.patch(url, headers={'If-Match': r.json()['_etag']},
                          json={'commentaire': "Can't touch this !"})
    assert r.status_code == 403, r.text


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


def test_create_site_bad_payload(administrateur, observateur, protocoles_base):
    # Register the observateur to a protocole
    protocole_id = str(protocoles_base[1]['_id'])
    r = observateur.put('/moi/protocoles/{}'.format(protocole_id))
    assert r.status_code == 200, r.text
    # Validate the user
    r = administrateur.put('/protocoles/{}/observateurs/{}'.format(
                           protocole_id, observateur.user_id))
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
