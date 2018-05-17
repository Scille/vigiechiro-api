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
from vigiechiro.app import app as flask_app
from vigiechiro.scripts import queuer


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
        '_updated': created,
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


def test_bad_change_proprietaire(clean_donnees, administrateur, participation_ready, taxons_base):
    observateur, protocole, site = participation_ready
    # Post participation
    participations_url = '/sites/{}/participations'.format(site['_id'])
    r = observateur.post(participations_url,
                         json={'date_debut': format_datetime(datetime.utcnow())})
    assert r.status_code == 201, r.text
    donnee_payload = {
        'proprietaire': observateur.user_id,
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
    r = administrateur.post('/participations/{}/donnees'.format(r.json()['_id']),
                            json=donnee_payload)
    assert r.status_code == 422, r.text


def test_new_donnee(clean_donnees, administrateur, participation_ready, taxons_base):
    observateur, protocole, site = participation_ready
    # Post participation
    participations_url = '/sites/{}/participations'.format(site['_id'])
    r = observateur.post(participations_url,
                         json={'date_debut': format_datetime(datetime.utcnow())})
    assert r.status_code == 201, r.text
    donnee_payload = {
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
    r = administrateur.post('/participations/{}/donnees'.format(r.json()['_id']),
                            json=donnee_payload)
    assert r.status_code == 201, r.text


def test_new_donnee_access(clean_donnees, participation_ready, administrateur, observateur_other):
    observateur, protocole, site = participation_ready
    # Post participation
    participations_url = '/sites/{}/participations'.format(site['_id'])
    r = observateur.post(participations_url,
                         json={'date_debut': format_datetime(datetime.utcnow())})
    assert r.status_code == 201, r.text
    # Admin (in fact script from tadaridaC) can post new donnees for observateur
    donnees_url = '/participations/{}/donnees'.format(r.json()['_id'])
    r = administrateur.post(donnees_url,
                            json={})
    assert r.status_code == 201, r.text
    # But other observateur cannot
    r = observateur_other.post(donnees_url,
                               json={})
    assert r.status_code == 403, r.text


def test_access(clean_donnees, donnee_env, observateur_other, validateur, administrateur):
    observateur, protocole, site, participation, donnee = donnee_env
    donnee_url = '/donnees/{}'.format(donnee['_id'])
    # Observateur wants to keep it work private
    r = administrateur.patch(observateur.url, json={'donnees_publiques': False})
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
    r = administrateur.patch(observateur.url, json={'donnees_publiques': True})
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
    r = administrateur.patch(observateur.url, json={'donnees_publiques': False})
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
    r = administrateur.patch(observateur.url, json={'donnees_publiques': True})
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
    # Do the actual validations
    r = observateur.patch(donnee_observation_url, json={
        'observateur_taxon': str(taxons_base[0]['_id']),
        'observateur_probabilite': 'PROBABLE'
    })
    assert r.status_code == 200, r.text
    r = validateur.patch(donnee_observation_url, json={
        'validateur_taxon': str(taxons_base[1]['_id']),
        'validateur_probabilite': 'SUR'
    })
    assert r.status_code == 200, r.text


def test_delete_site(donnee_env, taxons_base, observateur_other,
                     validateur, administrateur):
    observateur, protocole, site, participation, donnee = donnee_env
    r = administrateur.delete("/sites/%s" % site['_id'])
    assert r.status_code == 204, r.text
    r = administrateur.get("/sites/%s" % site['_id'])
    assert r.status_code == 404, r.text
    assert db.sites.find({'_id': site['_id']}).count() == 0
    # Test the task finishing the cleanup
    from vigiechiro.scripts.task_deleter import clean_deleted_site
    with flask_app.app_context():
        clean_deleted_site(site['_id'])
    assert db.participations.find({'site': site['_id']}).count() == 0
    assert db.donnees.find({'participation': participation['_id']}).count() == 0
    assert db.fichiers.find({'lien_participation': participation['_id']}).count() == 0
    # Cannot delete two times
    r = administrateur.delete("/sites/%s" % site['_id'])
    assert r.status_code == 404, r.text


def test_delete_participation(donnee_env, taxons_base, observateur_other,
                              validateur, administrateur):
    observateur, protocole, site, participation, donnee = donnee_env
    r = administrateur.delete("/participations/%s" % participation['_id'])
    assert r.status_code == 204, r.text
    r = administrateur.get("/participations/%s" % participation['_id'])
    assert r.status_code == 404, r.text
    assert db.participations.find({'_id': participation['_id']}).count() == 0
    # Test the task finishing the cleanup
    from vigiechiro.scripts.task_deleter import clean_deleted_participation
    with flask_app.app_context():
        clean_deleted_participation(participation['_id'])
    assert db.donnees.find({'participation': participation['_id']}).count() == 0
    assert db.fichiers.find({'lien_participation': participation['_id']}).count() == 0
    # Cannot delete two times
    r = administrateur.delete("/participations/%s" % participation['_id'])
    assert r.status_code == 404, r.text


def test_multi_bilan_triggered(clean_donnees, administrateur, participation_ready, taxons_base):
    with flask_app.app_context():
        observateur, protocole, site = participation_ready
        # Post participation
        participations_url = '/sites/{}/participations'.format(site['_id'])
        r = observateur.post(participations_url,
                             json={'date_debut': format_datetime(datetime.utcnow())})
        assert r.status_code == 201, r.text
        participation_id = r.json()['_id']

        queuer.collection.remove()

        # Create a donnees entry
        donnee_payload = {
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
        r = observateur.post('/participations/{}/donnees'.format(participation_id),
                                json=donnee_payload)
        assert r.status_code == 201, r.text
        donnee_id = r.json()['_id']

        # Bilan task should have been triggered
        assert queuer.get_pending_jobs().count() == 1
        queuer.collection.remove()
        assert queuer.get_pending_jobs().count() == 0

        # Modify donnees, bilan task is retriggered
        update_payload = {'observateur_taxon': str(taxons_base[1]['_id']),
                          'observateur_probabilite': 'SUR'}
        r = observateur.patch('donnees/{}/observations/0'.format(donnee_id),
                               json=update_payload)
        assert r.status_code == 200, r.text
        assert queuer.get_pending_jobs().count() == 1

        # Now re-modify donnees, given bilan task is already set, no should
        # task should be created
        r = observateur.patch('donnees/{}/observations/0'.format(donnee_id),
                               json=update_payload)
        assert r.status_code == 200, r.text
        assert queuer.get_pending_jobs().count() == 1
