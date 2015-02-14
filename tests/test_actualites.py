import pytest
from datetime import datetime

from common import db, observateur, validateur, administrateur, format_datetime, with_flask_context
from vigiechiro import settings
from vigiechiro.resources import utilisateurs as utilisateurs_resource

from test_protocoles import protocoles_base
from test_taxons import taxons_base


def test_actualites(observateur, administrateur, protocoles_base):
    protocole = protocoles_base[1]
    protocole_id = str(protocole['_id'])
    protocole_url = '/protocoles/{}/join'
    # Join a protocole
    r = observateur.post(protocole_url.format(protocole_id))
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
    r = administrateur.patch('/sites/{}/verrouille'.format(site_id),
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
    assert len(actualites) == 4, actualites
    actualites[0]['action'] == 'NOUVELLE_PARTICIPATION'
    actualites[1]['action'] == 'NOUVEAU_SITE'
    actualites[2]['action'] == 'VALIDATION_PROTOCOLE'
    actualites[3]['action'] == 'INSCRIPTION_PROTOCOLE'


def test_follow():
    pass
