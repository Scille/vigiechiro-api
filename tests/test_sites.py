import pytest
from bson import ObjectId
from datetime import datetime

from .common import db, administrateur, observateur, format_datetime
from .test_grille_stoc import grille_stoc
from .test_protocoles import protocoles_base, protocole_point_fixe
from .test_taxons import taxons_base


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


def test_list_own_sites(obs_sites_base, protocoles_base):
    observateur, sites_base = obs_sites_base
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
    # Only list the site of a single protocole
    r = observateur.get('/moi/sites',
                        params={'protocole': protocoles_base[2]['_id']})
    assert r.status_code == 200, r.text
    assert len(r.json()['_items']) == 0, r.json()


def test_list_protocole_sites(obs_sites_base, protocoles_base):
    observateur, sites_base = obs_sites_base
    protocole_id = sites_base[0]['protocole']
    url = 'protocoles/{}/sites'.format(protocole_id)
    r = observateur.get(url)
    assert r.status_code == 200, r.text
    items = r.json()['_items']
    assert len(items) == 2, r.json()
    # Resource contains expended version of fields protocole and grille_stoc
    for item in items:
        for field in ['protocole', 'grille_stoc']:
            assert field in item
            assert isinstance(item[field], dict), item
            assert '_id' in item[field], item
    # List another protocole with no sites
    url = 'protocoles/{}/sites'.format(protocoles_base[2]['_id'])
    r = observateur.get(url)
    assert r.status_code == 200, r.text
    assert len(r.json()['_items']) == 0, r.json()


def test_list_with_search(obs_sites_base):
    observateur, sites_base = obs_sites_base
    query = sites_base[0]['titre'].split('-')[-1]
    r = observateur.get('/sites', params={'q': query})
    assert r.status_code == 200, r.text
    assert len(r.json()['_items']) == 1, r.json()
    assert r.json()['_items'][0]['_id'] == str(sites_base[0]['_id'])


def test_list_with_grille_stoc(obs_sites_base):
    observateur, sites_base = obs_sites_base
    r = observateur.get('/sites', params={'grille_stoc': str(sites_base[0]['grille_stoc'])})
    assert r.status_code == 200, r.text
    assert len(r.json()['_items']) == 1, r.json()
    assert r.json()['_items'][0]['_id'] == str(sites_base[0]['_id'])
    # Unknown id should return an empty list
    r = observateur.get('/sites', params={'grille_stoc': '5516db691d41c8eac15ab672'})
    assert r.status_code == 200, r.text
    assert len(r.json()['_items']) == 0, r.json()
    # Try bad ids
    for bad_id in ['', 42, '*']:
        r = observateur.get('/sites', params={'grille_stoc': bad_id})
        assert r.status_code == 422, r.text


def test_not_registered_create_site(protocoles_base, observateur, administrateur):
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


def test_create_site_not_valide(observateur, protocoles_base):
    # Register the observateur to a protocole, but doesn't validate it
    protocole_id = str(protocoles_base[1]['_id'])
    r = observateur.put('/moi/protocoles/{}'.format(protocole_id))
    assert r.status_code == 200, r.text
    # Observateur is allowed to create multiple sites
    site_payload = {
        'protocole': protocole_id,
        'commentaire': 'My little site'
    }
    r = observateur.post('/sites', json=site_payload)
    assert r.status_code == 422, r.text


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
        'commentaire': 'My little site',
        'justification_non_aleatoire': 'dunno'
    }
    r = observateur.post('/sites', json=site_payload)
    assert r.status_code == 201, r.text
    r = observateur.get('/sites/' + r.json()['_id'])
    assert r.status_code == 200, r.text
    # Implicitly set the observateur in the created site
    assert r.json()['observateur']['_id'] == observateur.user_id
    assert r.json()['protocole']['_id'] == protocole_id

def test_create_custom_name_site(administrateur, observateur, protocoles_base):
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
        'titre': 'custom-title',
        'protocole': protocole_id,
        'commentaire': 'My little site',
        'justification_non_aleatoire': 'dunno'
    }
    r = observateur.post('/sites', json=site_payload)
    assert r.status_code == 201, r.text
    assert r.json()['titre'] == 'custom-title'

def test_same_grille_stoc_site(administrateur, protocole_point_fixe):
    protocole, taxon = protocole_point_fixe
    grilles = grille_stoc()
    # Register & validate admin in protocole
    protocole_id = str(protocole['_id'])
    r = administrateur.put('/moi/protocoles/{}'.format(protocole_id))
    assert r.status_code == 200, r.text
    site_payload = {
        'protocole': protocole_id,
        'commentaire': 'My little site',
        'grille_stoc': str(grilles[0]['_id'])
    }
    r = administrateur.post('/sites', json=site_payload)
    assert r.status_code == 201, r.text
    assert r.json()['titre'] == '{}-{}'.format(protocole['titre'], grilles[0]['numero'])
    # Try to create another site on the same grille
    r = administrateur.post('/sites', json=site_payload)
    assert r.status_code == 422, r.text


def test_naming_autoinc(administrateur, protocoles_base):
    # Get the current counter
    increments = db.configuration.find_one({'name': 'increments'})
    assert 'protocole_routier_count' in increments
    # Register the admin to a protocole
    protocole = protocoles_base[1]
    protocole_id = str(protocole['_id'])
    r = administrateur.put('/moi/protocoles/{}'.format(protocole_id))
    assert r.status_code == 200, r.text
    # Create a new site
    r = administrateur.post('/sites', json={'protocole': protocole_id})
    assert r.status_code == 201, r.text
    site_url = '/sites/{}'.format(r.json()['_id'])
    site1 = r.json()
    # Create another site
    r = administrateur.post('/sites', json={'protocole': protocole_id})
    assert r.status_code == 201, r.text
    site_url = '/sites/{}'.format(r.json()['_id'])
    site2 = r.json()
    # Check the given titles
    assert site1['titre'] == "{}-{}".format(protocole['titre'],
        increments['protocole_routier_count'] + 1)
    assert site2['titre'] == "{}-{}".format(protocole['titre'],
        increments['protocole_routier_count'] + 2)


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
    # Opportuniste participation are now allowed : anyone can create a participation in a site
    # # Now observateur cannot use this site anymore
    # # TODO : test participation
    # r = observateur.post('{}/participations'.format(site_url),
    #                      json={'date_debut': format_datetime(datetime.utcnow())})
    # assert r.status_code == 422, r.text


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


def test_create_site_bad_payload(administrateur, observateur, protocoles_base):
    # Register the observateur to a protocole
    protocole_id = str(protocoles_base[1]['_id'])
    r = observateur.put('/moi/protocoles/{}'.format(protocole_id))
    assert r.status_code == 200, r.text
    # Validate the user
    r = administrateur.put('/protocoles/{}/observateurs/{}'.format(
                           protocole_id, observateur.user_id))
    assert r.status_code == 200, r.text
    # First create a site
    site_payload = {"protocole": protocole_id}
    r = observateur.post('/sites', json=site_payload)
    assert r.status_code == 201, r.text
    # Site payload's geojson doesn't match expected geojson schema
    localite_url = '/sites/{}/localites'.format(r.json()['_id'])
    for bad_geometrie in [
        {"type":"Point", "coordinates":[48.862004474432936,2.338886260986328]},
        {"type":"Point", "coordinates":[48.877812415009195,2.3639488220214844]},
        {"type":"LineString", "coordinates":[
            [48.86539231071163,2.353992462158203],
            [48.87239311228893,2.353649139404297],
            [48.87736082887189,2.344379425048828]]
        }]:
        r = observateur.put(localite_url, json={
            'localites': [{'nom': 'bad_localite', 'geometries': bad_geometrie}]
        })
        assert r.status_code == 422, r.text


def create_site_with_localite(protocole_id, observateur, site_id=None):
    if not site_id:
        # First create a site
        site_payload = {"protocole": protocole_id}
        r = observateur.post('/sites', json=site_payload)
        assert r.status_code == 201, r.text
        site_url = '/sites/{}'.format(r.json()['_id'])
    else:
        site_url = '/sites/{}'.format(site_id)
    localite_url = site_url + '/localites'
    geometries = {'type': 'GeometryCollection',
                  'geometries': [
                      {"type":"Point", "coordinates":[48.862004474432936,2.338886260986328]},
                      {"type":"Point", "coordinates":[48.877812415009195,2.3639488220214844]},
                      {"type":"LineString", "coordinates":[
                          [48.86539231071163,2.353992462158203],
                          [48.87239311228893,2.353649139404297],
                          [48.87736082887189,2.344379425048828]]
                      }
                    ]
                }
    # Add localite
    r = observateur.put(localite_url,
        json={'localites': [{'nom': 'localite1', 'geometries': geometries}]})
    assert r.status_code == 200, r.text
    return r.json()


def test_localite_name_unicity(observateur, administrateur, protocoles_base):
    protocole_id = str(protocoles_base[1]['_id'])
    # Register the observateur to a protocole
    protocole_id = str(protocoles_base[1]['_id'])
    r = observateur.put('/moi/protocoles/{}'.format(protocole_id))
    assert r.status_code == 200, r.text
    # Validate the user
    r = administrateur.put('/protocoles/{}/observateurs/{}'.format(
                           protocole_id, observateur.user_id))
    assert r.status_code == 200, r.text
    # First create a site
    site_payload = {"protocole": protocole_id}
    r = observateur.post('/sites', json=site_payload)
    assert r.status_code == 201, r.text
    site_url = '/sites/{}'.format(r.json()['_id'])
    localite_url = site_url + '/localites'
    geometries = {'type': 'GeometryCollection',
                  'geometries': [
                      {"type":"Point", "coordinates":[48.862004474432936,2.338886260986328]},
                      {"type":"Point", "coordinates":[48.877812415009195,2.3639488220214844]},
                      {"type":"LineString", "coordinates":[
                          [48.86539231071163,2.353992462158203],
                          [48.87239311228893,2.353649139404297],
                          [48.87736082887189,2.344379425048828]]
                      }
                    ]
                }
    # Cannot add localite with the same name
    r = observateur.put(localite_url,
        json={'localites': [{'nom': 'localite1', 'geometries': geometries},
                            {'nom': 'localite2', 'geometries': geometries},
                            {'nom': 'localite1', 'geometries': geometries}]})
    assert r.status_code == 422, r.text
    # Now add valid localite
    r = observateur.put(localite_url,
        json={'localites': [{'nom': 'localite1', 'geometries': geometries}]})
    assert r.status_code == 200, r.text
    # Put replace data, so we can replace the same localite name
    r = observateur.put(localite_url,
        json={'localites': [{'nom': 'localite1', 'geometries': geometries}]})
    assert r.status_code == 200, r.text
    # Make sure only one localite is present
    r = observateur.get(site_url)
    assert r.status_code == 200, r.text
    assert r.json()['localites'] == [{'nom': 'localite1', 'geometries': geometries}]


def test_create_site_with_localite(administrateur, observateur, protocoles_base):
    # Register the observateur to a protocole
    protocole_id = str(protocoles_base[1]['_id'])
    r = observateur.put('/moi/protocoles/{}'.format(protocole_id))
    assert r.status_code == 200, r.text
    # Validate the user
    r = administrateur.put('/protocoles/{}/observateurs/{}'.format(
                           protocole_id, observateur.user_id))
    assert r.status_code == 200, r.text
    site = create_site_with_localite(protocole_id, observateur)
    # Make sure localite is present
    site_url = '/sites/{}'.format(site['_id'])
    r = observateur.get(site_url)
    assert r.status_code == 200, r.text
    assert len(r.json()['localites']) == 1


def test_add_and_remove_localites(administrateur, observateur, protocoles_base):
    def check_localite_count(x):
        r = observateur.get(site_url)
        assert r.status_code == 200, r.text
        assert len(r.json().get('localites', [])) == x
    # Register the observateur to a protocole
    protocole_id = str(protocoles_base[1]['_id'])
    r = observateur.put('/moi/protocoles/{}'.format(protocole_id))
    assert r.status_code == 200, r.text
    # Validate the user
    r = administrateur.put('/protocoles/{}/observateurs/{}'.format(
                           protocole_id, observateur.user_id))
    assert r.status_code == 200, r.text
    site = create_site_with_localite(protocole_id, observateur)
    # Make sure localite is present
    site_url = '/sites/{}'.format(site['_id'])
    check_localite_count(1)
    # Delete the localite
    r = observateur.put(site_url + '/localites', json={'localites': []})
    assert r.status_code == 200, r.text
    # No more localites in the site
    check_localite_count(0)
    # Add back a localite and lock the site
    site = create_site_with_localite(protocole_id, observateur, site['_id'])
    check_localite_count(1)
    r = administrateur.patch(site_url, json={'verrouille': True})
    assert r.status_code == 200, r.text
    # Now owner cannot remove localites
    r = observateur.put(site_url + '/localites', json={'localites': []})
    assert r.status_code == 403, r.text
    check_localite_count(1)
