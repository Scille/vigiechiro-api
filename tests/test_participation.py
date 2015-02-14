import requests
import pytest
import base64
import json
from bson import ObjectId
from datetime import datetime, timedelta

from common import (db, observateur, observateur_other, validateur,
                    administrateur, format_datetime, with_flask_context)
from vigiechiro import settings
from vigiechiro.resources import utilisateurs as utilisateurs_resource
from test_protocoles import protocoles_base
from test_taxons import taxons_base
from test_sites import obs_sites_base


@pytest.fixture
def clean_participations(request):
    def finalizer():
        db.participations.remove()
    request.addfinalizer(finalizer)
    return None


@pytest.fixture
def participation_ready(clean_participations, obs_sites_base, administrateur):
    observateur, sites_base = obs_sites_base
    site = sites_base[0]
    protocole = site['protocole']
    protocole = db.protocoles.find_one({'_id': site['protocole']})
    # Make sure observateur is validate
    r = administrateur.patch(observateur.url,
                             headers={'If-Match': observateur.user['_etag']},
                             json={'protocoles': [{'protocole': str(protocole['_id']),
                                                   'date_inscription': format_datetime(datetime.utcnow()),
                                                   'valide': True}]})
    assert r.status_code == 200, r.text
    # Lock site
    r = administrateur.patch('/sites/{}/verrouille'.format(site['_id']),
                             json={'verrouille': True})
    assert r.status_code == 200, r.text
    observateur.update_user()
    return (observateur, protocole, site)


def test_non_valide_observateur(clean_participations, obs_sites_base, administrateur):
    # Observateur subscribe to protocole and create a site but is not yet
    # validated
    observateur, sites_base = obs_sites_base
    site = sites_base[0]
    protocole_id = str(site['protocole'])
    # Make sure observateur is not validate in the protocole
    r = administrateur.patch(observateur.url,
                             headers={'If-Match': observateur.user['_etag']},
                             json={'protocoles': [{'protocole': protocole_id,
                                                   'date_inscription': format_datetime(datetime.utcnow()),
                                                   'valide': False}]})
    assert r.status_code == 200, r.text
    # Cannot post any participation
    r = observateur.post('/sites/{}/participations'.format(site['_id']),
                         json={'date_debut': format_datetime(datetime.utcnow())})
    assert r.status_code == 422, r.text
    # Observateur is finally validated
    r = administrateur.put('/protocoles/{}/observateurs/{}'.format(
        protocole_id, observateur.user_id), json={'valide': True})
    assert r.status_code == 200, r.text
    # Still cannot post any participation (site not verouille)
    r = observateur.post('/sites/{}/participations'.format(site['_id']),
                         json={'date_debut': format_datetime(datetime.utcnow())})
    assert r.status_code == 422, r.text
    r = administrateur.patch('/sites/{}/verrouille'.format(site['_id']),
                             json={'verrouille': True})
    assert r.status_code == 200, r.text
    # Post participation is now ok
    r = observateur.post('/sites/{}/participations'.format(site['_id']),
                         json={'date_debut': format_datetime(datetime.utcnow())})
    assert r.status_code == 201, r.text


def test_messages(participation_ready, observateur_other, validateur, administrateur):
    observateur, protocole, site = participation_ready
    # Post participation
    r = observateur.post('/sites/{}/participations'.format(site['_id']),
                         json={'date_debut': format_datetime(datetime.utcnow())})
    assert r.status_code == 201, r.text
    # Other observateurs cannot post comments
    participation_id = r.json()['_id']
    msg_url = '/participations/{}/messages'.format(participation_id)
    r = observateur_other.post(msg_url, json={'message': 'not allowed'})
    assert r.status_code == 403, r.text
    # Admin, validateur and owner can
    r = observateur.post(msg_url, json={'message': 'owner msg'})
    assert r.status_code == 201, r.text
    r = validateur.post(msg_url, json={'message': 'validateur msg'})
    assert r.status_code == 201, r.text
    r = administrateur.post(msg_url, json={'message': 'administrateur msg'})
    assert r.status_code == 201, r.text
    # Check back the comments
    r = observateur.get('/participations/{}'.format(participation_id))
    assert r.status_code == 200, r.text
    messages = r.json()['messages']
    assert len(messages) == 3, messages
