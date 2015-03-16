import pytest
import json
from datetime import datetime, timedelta

from .common import (db, observateur, observateur_other, validateur,
                     administrateur, format_datetime, with_flask_context)
from vigiechiro import settings
from vigiechiro.resources import utilisateurs as utilisateurs_resource
from .test_protocoles import protocoles_base
from .test_taxons import taxons_base
from .test_sites import obs_sites_base
from .test_fichiers import (file_uploaded, custom_upload_file, clean_fichiers,
                            file_init, file_uploaded)

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
    db.utilisateurs.update({'_id': observateur.user['_id']},
        {'$set': {
            'protocoles': [{
                'protocole': protocole['_id'],
                'date_inscription': format_datetime(datetime.utcnow()),
                'valide': True
                }]
            }
        })
    # Lock site
    r = administrateur.patch('/sites/{}'.format(site['_id']),
                             json={'verrouille': True})
    assert r.status_code == 200, r.text
    observateur.update_user()
    return (observateur, protocole, site)


def test_pieces_jointes_access(participation_ready, file_uploaded,
                              observateur_other, administrateur, validateur):
    observateur, protocole, site = participation_ready
    # Post participation
    r = observateur.post('/sites/{}/participations'.format(site['_id']),
                         json={'date_debut': format_datetime(datetime.utcnow())})
    assert r.status_code == 201, r.text
    participations_url = '/participations/{}'.format(r.json()['_id'])
    # Observateur wants to keep it work private
    r = observateur.patch('/moi', json={'donnees_publiques': False})
    assert r.status_code == 200, r.text
    # Other observateurs still can see it participations
    r = observateur_other.get(participations_url)
    assert r.status_code == 200, r.text
    # But he can't see it pieces_jointes
    r = observateur_other.get(participations_url + '/pieces_jointes')
    assert r.status_code == 403, r.text
    # Validateur and admin still can
    r = validateur.get(participations_url + '/pieces_jointes')
    assert r.status_code == 200, r.text
    r = administrateur.get(participations_url + '/pieces_jointes')
    assert r.status_code == 200, r.text
    # Now switch back to public
    r = observateur.patch('/moi', json={'donnees_publiques': True})
    assert r.status_code == 200, r.text
    # Other observateur are now allowed
    r = observateur_other.get(participations_url + '/pieces_jointes')
    assert r.status_code == 200, r.text


def test_participation(participation_ready, file_uploaded, observateur_other):
    observateur, protocole, site = participation_ready
    # Post participation
    participations_url = '/sites/{}/participations'.format(site['_id'])
    r = observateur.post(participations_url,
                         json={'date_debut': format_datetime(datetime.utcnow())})
    assert r.status_code == 201, r.text
    participation = r.json()
    sent_pieces_jointes = set()
    # Send files
    r = observateur.get('/participations/{}'.format(participation['_id']))
    assert r.status_code == 200, r.text
    pieces_jointes_url = '/participations/{}/pieces_jointes'.format(participation['_id'])
    r = observateur.put(pieces_jointes_url,
                        json={'photos': [file_uploaded['_id']]})
    assert r.status_code == 200, r.text
    # Send multiple files with different allowed mime types
    photos_ids = []
    for i, mime in enumerate(['image/bmp', 'image/png', 'image/jpg']):
        res = custom_upload_file({'titre': 'file_photo_{}'.format(i), 'mime': mime}, observateur)
        photos_ids.append(res['_id'])
    ta_ids = []
    for i, mime in enumerate(['application/ta', 'application/tac']):
        res = custom_upload_file({'titre': 'file_ta_{}'.format(i), 'mime': mime}, observateur)
        ta_ids.append(res['_id'])
    wav_ids = []
    for i, mime in enumerate(['audio/wav', 'audio/x-wav']):
        res = custom_upload_file({'titre': 'file_wav_{}'.format(i), 'mime': mime}, observateur)
        wav_ids.append(res['_id'])
    r = observateur.put(pieces_jointes_url,
                        json={'wav': wav_ids, 'ta': ta_ids, 'photos': photos_ids })
    photos_ids.append(file_uploaded['_id'])
    assert r.status_code == 200, r.text
    # Finally display all the pieces_jointes
    r = observateur.get(pieces_jointes_url)
    assert r.status_code == 200, r.text
    pieces_jointes = r.json()
    assert 'ta' in pieces_jointes
    assert 'wav' in pieces_jointes
    assert 'photos' in pieces_jointes
    assert len(pieces_jointes['ta']) == len(ta_ids)
    # Bonus effect : pieces_jointes sould be marked to execute tadarida on them
    for pj in pieces_jointes['ta']:
        assert pj['_id'] in ta_ids
        assert pj['require_process'] == 'tadarida_c'
    assert len(pieces_jointes['wav']) == len(wav_ids)
    for pj in pieces_jointes['wav']:
        assert pj['_id'] in wav_ids
        assert pj['require_process'] == 'tadarida_d'
    assert len(pieces_jointes['photos']) == len(photos_ids)
    for pj in pieces_jointes['photos']:
        assert pj['_id'] in photos_ids
        assert 'require_process' not in pj


def test_participation_bad_file(participation_ready, file_init):
    observateur, protocole, site = participation_ready
    # Post participation
    participations_url = '/sites/{}/participations'.format(site['_id'])
    r = observateur.post(participations_url,
                         json={'date_debut': format_datetime(datetime.utcnow())})
    assert r.status_code == 201, r.text
    participation = r.json()
    # Try to send a dummy file id as piece_jointe
    pieces_jointes_url = '/participations/{}/pieces_jointes'.format(participation['_id'])
    r = observateur.put(pieces_jointes_url,
                        json={'photos': ["54ecaa5e13adf24668712f76"]})
    # Try to send a non-uploaded file as piece_jointe
    pieces_jointes_url = '/participations/{}/pieces_jointes'.format(participation['_id'])
    r = observateur.put(pieces_jointes_url,
                        json={'photos': [file_init['_id']]})
    assert r.status_code == 422, r.text
    # Try to send a file with bad mime type
    for i, mime in enumerate(['application/json', '', 'application/octet-stream',
                              'application/zip', 'audio/mpeg', 'text/plain']):
        # Create file & finish it upload
        res = custom_upload_file({'titre': 'file_{}'.format(i), 'mime': mime}, observateur)
        r = observateur.put(pieces_jointes_url,
                            json={'photos': [res['_id']]})
        assert r.status_code == 422, r.text


def test_non_valide_observateur(clean_participations, obs_sites_base, administrateur):
    # Observateur subscribe to protocole and create a site but is not yet
    # validated
    observateur, sites_base = obs_sites_base
    site = sites_base[0]
    protocole_id = str(site['protocole'])
    # Make sure observateur is not validate in the protocole
    db.utilisateurs.update(
        {'_id': observateur.user['_id'], 'protocoles.protocole': site['protocole']},
        {'$set': {'protocoles.$.valide': False}})
    observateur.update_user()
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
    r = administrateur.patch('/sites/{}'.format(site['_id']),
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
    r = observateur_other.put(msg_url, json={'message': 'not allowed'})
    assert r.status_code == 403, r.text
    # Admin, validateur and owner can
    r = observateur.put(msg_url, json={'message': 'owner msg'})
    assert r.status_code == 200, r.text
    r = validateur.put(msg_url, json={'message': 'validateur msg'})
    assert r.status_code == 200, r.text
    r = administrateur.put(msg_url, json={'message': 'administrateur msg'})
    assert r.status_code == 200, r.text
    # Check back the comments
    r = observateur.get('/participations/{}'.format(participation_id))
    assert r.status_code == 200, r.text
    messages = r.json()['messages']
    assert len(messages) == 3, messages
