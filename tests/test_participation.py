import requests
from pymongo import MongoClient
import pytest
from datetime import datetime

from common import db, administrateur, validateur, observateur, eve_post_internal, format_datetime
from test_protocole import protocoles_base
from test_taxon import taxons_base
from test_site import sites_base


@pytest.fixture
def clean_participations(request):
    def finalizer():
        db.participations.remove()
    request.addfinalizer(finalizer)
    return None


@pytest.fixture
def participation_ready(
        clean_participations,
        sites_base,
        observateur,
        administrateur):
    site = sites_base[0]
    protocole = site['protocole']
    protocole = db.protocoles.find_one({'_id': site['protocole']})
    r = administrateur.patch(observateur.url,
                             headers={'If-Match': observateur.user['_etag']},
                             json={'protocoles': {str(protocole['_id']): {'valide': True}}})
    assert r.status_code == 200, r.text
    observateur.update_user()
    return (observateur, protocole, site)


def test_non_valide_observateur(
        clean_participations,
        sites_base,
        observateur,
        administrateur):
    # Observateur subscribe to protocole and is assigned to a site but is not
    # validated
    site = sites_base[0]
    protocole_id = str(site['protocole'])
    etag = site['_etag']
    r = administrateur.patch('/sites/' + str(site['_id']),
                             headers={'If-Match': etag},
                             json={'observateur': observateur.user_id})
    assert r.status_code == 200, r.text
    r = observateur.patch(observateur.url,
                          headers={'If-Match': observateur.user['_etag']},
                          json={'protocoles': {protocole_id: {}}})
    assert r.status_code == 200, r.text
    # Cannot post any participation
    r = observateur.post('/participations',
                         json={'date_debut': format_datetime(datetime.utcnow()),
                               'observateur': observateur.user_id,
                               'protocole': protocole_id,
                               'site': str(site['_id'])})
    assert r.status_code == 422, r.text
    # Observateur is finally validated
    observateur.update_user()
    r = administrateur.patch(
        observateur.url,
        headers={
            'If-Match': observateur.user['_etag']},
        json={
            'protocoles': {
                protocole_id: {
                    'valide': True}}})
    assert r.status_code == 200, r.text
    # Post participation is now ok
    r = observateur.post('/participations',
                         json={'date_debut': format_datetime(datetime.utcnow()),
                               'observateur': observateur.user_id,
                               'protocole': protocole_id,
                               'site': str(site['_id'])})
    observateur.update_user()
    assert r.status_code == 201, r.text


def test_wrong_protocole(participation_ready, protocoles_base):
    # Trying to post a valid participation with dummy protocole...
    observateur, protocole, site = participation_ready
    bad_protocole_id = str(protocoles_base[2]['_id'])
    r = observateur.post('/participations',
                         json={'date_debut': format_datetime(datetime.utcnow()),
                               'observateur': observateur.user_id,
                               'protocole': bad_protocole_id,
                               'site': str(site['_id'])})
    assert r.status_code == 422, r.text


def test_wrong_site(participation_ready, sites_base):
    # Trying to post a valid participation with dummy site...
    observateur, protocole, site = participation_ready
    bad_site_id = str(sites_base[1]['_id'])
    r = observateur.post('/participations',
                         json={'date_debut': format_datetime(datetime.utcnow()),
                               'observateur': observateur.user_id,
                               'protocole': str(protocole['_id']),
                               'site': bad_site_id})
    assert r.status_code == 422, r.text


def test_wrong_observateur(
        participation_ready,
        protocoles_base,
        validateur,
        administrateur):
    # Observateur cannot post in the name of someone else
    real_observateur, protocole, site = participation_ready
    r = real_observateur.post(
        '/participations',
        json={
            'date_debut': format_datetime(datetime.utcnow()),
            'observateur': validateur.user_id,
            'protocole': str(
                protocole['_id']),
            'site': str(
                site['_id'])})
    assert r.status_code == 422, r.text
    # Admin can post in the name of others
    r = administrateur.post(
        '/participations',
        json={
            'date_debut': format_datetime(datetime.utcnow()),
            'observateur': real_observateur.user_id,
            'protocole': str(
                protocole['_id']),
            'site': str(
                site['_id'])})
    assert r.status_code == 201, r.text
