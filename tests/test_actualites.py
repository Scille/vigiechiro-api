import pytest
from datetime import datetime
from time import sleep

from common import db, observateur, validateur, administrateur, format_datetime, with_flask_context
from vigiechiro import settings
from vigiechiro.resources import utilisateurs as utilisateurs_resource

from test_protocoles import protocoles_base
from test_taxons import taxons_base


@pytest.fixture
def clean_actualites(request):
    db.actualites.remove()
    def finalizer():
        db.actualites.remove()
    request.addfinalizer(finalizer)


def test_actualites(clean_actualites, observateur,
                     administrateur, protocoles_base):
    protocole = protocoles_base[1]
    protocole_id = str(protocole['_id'])
    protocole_url = '/moi/protocoles/{}'
    # Join a protocole
    r = observateur.put(protocole_url.format(protocole_id))
    assert r.status_code == 200, r.text
    observateur.update_user()
    # Now validate the user
    r = administrateur.put('/protocoles/{}/observateurs/{}'.format(
        protocole_id, observateur.user_id), json={'valide': True})
    assert r.status_code == 200, r.text
    # Create site
    r = observateur.post('/sites', json={
        'protocole': protocole_id
        })
    assert r.status_code == 201, r.text
    site_id = r.json()['_id']
    # Lock the site
    r = administrateur.patch('/sites/{}'.format(site_id),
        json={'verrouille': True})
    assert r.status_code == 200, r.text
    # Create a participation
    r = observateur.post('/sites/{}/participations'.format(site_id),
                         json={'date_debut': format_datetime(datetime.utcnow())})
    # Now check the actualities to retrieve the actions
    r = observateur.get('/moi/actualites')
    assert r.status_code == 200, r.text
    actualites = r.json()['_items']
    print(actualites)
    assert len(actualites) == 3, actualites
    actualites[0]['action'] == 'NOUVELLE_PARTICIPATION'
    actualites[1]['action'] == 'NOUVEAU_SITE'
    actualites[2]['action'] == 'INSCRIPTION_PROTOCOLE'


def test_list_protocole_users(clean_actualites, protocoles_base,
                              observateur, administrateur):
    protocole = protocoles_base[1]
    protocole_id = str(protocole['_id'])
    another_protocole = protocoles_base[2]
    another_protocole_id = str(another_protocole['_id'])
    # Join a protocole
    r = observateur.put('/moi/protocoles/' + protocole_id)
    assert r.status_code == 200, r.text
    sleep(1)
    r = administrateur.put('/moi/protocoles/' + protocole_id)
    assert r.status_code == 200, r.text
    sleep(1)
    # Join another protocole
    r = observateur.put('/moi/protocoles/' + another_protocole_id)
    assert r.status_code == 200, r.text
    sleep(1)
    # Validate protocole only for the admin
    validate_url = '/protocoles/{}/observateurs/{}'.format(
        protocole_id, administrateur.user_id)
    r = administrateur.put(validate_url, json={'valide': True})
    assert r.status_code == 200, r.text
    administrateur.update_user()
    observateur.update_user()
    # Now have a look at the actualities
    r = observateur.get('/actualites/validations')
    assert r.status_code == 200, r.text
    items = r.json()['_items']
    assert len(items) == 3
    assert not [i for i in items if i.get('action', None) != 'INSCRIPTION_PROTOCOLE']
    # List of element :
    # - administrateur is validated in protocole
    # - observateur has joined another_protocole
    # - observateur has joined protocole
    assert items[0]['sujet']['_id'] == administrateur.user_id
    assert items[0]['protocole']['_id'] == protocole_id
    assert items[1]['sujet']['_id'] == observateur.user_id
    assert items[1]['protocole']['_id'] == another_protocole_id
    assert items[2]['sujet']['_id'] == observateur.user_id
    assert items[2]['protocole']['_id'] == protocole_id
    print(items)


def test_follow():
    pass
