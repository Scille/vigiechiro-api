import requests
import pytest
from bson import ObjectId
from uuid import uuid4
from datetime import datetime

from .common import (db, administrateur, validateur, observateur,
                     observateur_other, format_datetime)
from .test_taxons import taxons_base
from .test_participation import participation_ready, clean_participations
from .test_protocoles import protocoles_base
from .test_taxons import taxons_base
from .test_sites import obs_sites_base

from vigiechiro import settings


@pytest.fixture
def donnee_env(request, participation_ready, taxons_base):
    observateur, protocole, site = participation_ready
    # Post participation
    participations_url = '/sites/{}/participations'.format(site['_id'])
    r = observateur.post(participations_url,
                         json={'date_debut': format_datetime(datetime.utcnow())})
    assert r.status_code == 201, r.text
    participation = r.json()
    created = format_datetime(datetime.utcnow())
    donnee_payload = {
        '_created': created,
        '_udpated': created,
        '_etag': uuid4().hex,
        'proprietaire': observateur.user['_id'],
        'participation': ObjectId(participation['_id']),
        'observations': [
            {
                'temps_debut': 102,
                'temps_fin': 1300,
                'frequence_mediane': 10000000,
                'tadarida_taxon': taxons_base[1]['_id'],
                'tadarida_probabilite': 70,
                'tadarida_taxon_autre': [
                    {
                        'taxon': taxons_base[2]['_id'],
                        'probabilite': 30
                    },
                ]
            }
        ]
    }
    donnee_payload['_id'] = db.donnees.insert(donnee_payload)
    def finalizer():
        db.donnees.remove({'_id': donnee_payload['_id']})
    request.addfinalizer(finalizer)
    return participation_ready + (participation, donnee_payload)


@pytest.fixture
def clean_donnees():
    db.donnees.remove({})


def test_new_donnee_required(administrateur):
    # Try to create a donnee with no participation
    r = administrateur.post('/donnees', json={})
    assert r.status_code == 422, r.text


def test_new_donnee(clean_donnees, administrateur, participation_ready, taxons_base):
    observateur, protocole, site = participation_ready
    # Post participation
    participations_url = '/sites/{}/participations'.format(site['_id'])
    r = observateur.post(participations_url,
                         json={'date_debut': format_datetime(datetime.utcnow())})
    assert r.status_code == 201, r.text
    donnee_payload = {
        'proprietaire': observateur.user_id,
        'participation': r.json()['_id'],
        'observations': [
            {
                'temps_debut': 102,
                'temps_fin': 1300,
                'frequence_mediane': 10000000,
                'tadarida_taxon': str(taxons_base[1]['_id']),
                'tadarida_probabilite': 70,
                'tadarida_taxon_autre': [
                    {
                        'taxon': str(taxons_base[2]['_id']),
                        'probabilite': 30
                    },
                ]
            }
        ]
    }
    r = administrateur.post('/donnees', json=donnee_payload)
    assert r.status_code == 201, r.text


def test_new_donnee_access(clean_donnees, participation_ready):
    # Only admin (in fact script from tadaridaC) can post new donnees
    observateur, protocole, site = participation_ready
    # Post participation
    participations_url = '/sites/{}/participations'.format(site['_id'])
    r = observateur.post(participations_url,
                         json={'date_debut': format_datetime(datetime.utcnow())})
    assert r.status_code == 201, r.text
    r = observateur.post('/donnees', json={'participation': r.json()['_id']})
    assert r.status_code == 403, r.text


def test_access(donnee_env, observateur_other, validateur, administrateur):
    observateur, protocole, site, participation, donnee = donnee_env
    donnee_url = '/donnees/{}'.format(donnee['_id'])
    # Observateur wants to keep it work private
    r = observateur.patch('/moi', json={'donnees_publiques': False})
    assert r.status_code == 200, r.text
    # Other observateurs can't see it
    r = observateur_other.get(donnee_url)
    assert r.status_code == 403, r.text
    r = observateur_other.get('/donnees')
    assert r.status_code == 200, r.text
    assert(len(r.json()['_items']) == 0), r.json()
    # Validateur and admin still can
    r = validateur.get(donnee_url)
    assert r.status_code == 200, r.text
    r = administrateur.get(donnee_url)
    assert r.status_code == 200, r.text
    r = validateur.get('/donnees')
    assert r.status_code == 200, r.text
    assert(len(r.json()['_items']) == 1), r.json()
    # Now switch back to public
    r = observateur.patch('/moi', json={'donnees_publiques': True})
    assert r.status_code == 200, r.text
    # Other observateur are now allowed
    r = observateur_other.get(donnee_url)
    assert r.status_code == 200, r.text
    r = observateur_other.get('/donnees')
    assert r.status_code == 200, r.text
    assert(len(r.json()['_items']) == 1), r.json()


def test_messages(donnee_env, observateur_other, validateur, administrateur):
    observateur, protocole, site, participation, donnee = donnee_env
    donnee_url = '/donnees/{}'.format(donnee['_id'])
    donnee_comment_url = donnee_url + '/observations/0/messages'
    # Observateur wants to keep it work private
    r = observateur.patch('/moi', json={'donnees_publiques': False})
    # Make sure he can still comment
    r = observateur.put(donnee_comment_url, json={'message': "What do you think of this ?"})
    assert r.status_code == 200, r.text
    # Other observateurs can't comment
    r = observateur_other.put(donnee_comment_url, json={'message': "can't touch this !"})
    assert r.status_code == 403, r.text
    # Validateur and admin still can
    r = validateur.put(donnee_comment_url, json={'message': "validateur can comment"})
    assert r.status_code == 200, r.text
    r = administrateur.put(donnee_comment_url, json={'message': "administrateur can comment"})
    assert r.status_code == 200, r.text
    # Now switch back to public
    r = observateur.patch('/moi', json={'donnees_publiques': True})
    assert r.status_code == 200, r.text
    # Other observateur are now allowed
    r = observateur_other.put(donnee_comment_url, json={'message': "finally I can comment !"})
    assert r.status_code == 200, r.text
    # Retrieve the messages
    r = observateur.get(donnee_url)
    assert r.status_code == 200, r.text
    assert len(r.json()['observations'][0]['messages']) == 4
    msg_thread = [m['message'] for m in r.json()['observations'][0]['messages']]
    assert msg_thread == [
        "What do you think of this ?",
        "validateur can comment",
        "administrateur can comment",
        "finally I can comment !"
    ]


def test_validation(donnee_env, taxons_base, observateur_other,
                    validateur, administrateur):
    observateur, protocole, site, participation, donnee = donnee_env
    donnee_url = '/donnees/{}'.format(donnee['_id'])
    donnee_observation_url = donnee_url + '/observations/0'
    # Try with no probabilite
    r = observateur.patch(donnee_observation_url, json={
        'observateur_taxon': str(taxons_base[1]['_id'])
    })
    assert r.status_code == 422, r.text
    # Missing taxon
    r = observateur.patch(donnee_observation_url, json={
        'observateur_probabilite': 'SUR'
    })
    assert r.status_code == 422, r.text
    # Try bad probabilite
    for bad_proba in ['no', 'SUREEE', '*', 1]:
        r = observateur.patch(donnee_observation_url, json={
            'observateur_taxon': str(taxons_base[1]['_id']),
            'observateur_probabilite': bad_proba
        })
        assert r.status_code == 422, r.text
    # Owner cannot patch validateur_taxon
    r = observateur.patch(donnee_observation_url, json={
        'validateur_taxon': str(taxons_base[1]['_id']),
        'validateur_probabilite': 'SUR'
    })
    assert r.status_code == 403, r.text
    # Other observateurs cannot do anything
    r = observateur_other.patch(donnee_observation_url, json={
        'observateur_taxon': str(taxons_base[1]['_id']),
        'observateur_probabilite': 'SUR'
    })
    assert r.status_code == 403, r.text
    r = observateur_other.patch(donnee_observation_url, json={
        'validateur_taxon': str(taxons_base[1]['_id']),
        'validateur_probabilite': 'SUR'
    })
    assert r.status_code == 403, r.text
    # Validateur/admin cannot patch observateur_taxon
    r = administrateur.patch(donnee_observation_url, json={
        'observateur_taxon': str(taxons_base[1]['_id']),
        'observateur_probabilite': 'SUR'
    })
    assert r.status_code == 403, r.text
    r = validateur.patch(donnee_observation_url, json={
        'observateur_taxon': str(taxons_base[1]['_id']),
        'observateur_probabilite': 'SUR'
    })
    assert r.status_code == 403, r.text
