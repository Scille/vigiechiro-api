import requests
from pymongo import MongoClient
import pytest
from uuid import uuid4
from datetime import datetime

from .common import db, administrateur, validateur, observateur, observateur_other, format_datetime
from .test_sites import obs_sites_base
from .test_protocoles import protocoles_base
from .test_taxons import taxons_base
from vigiechiro import settings
from vigiechiro.resources import fichiers as fichiers_resource


@pytest.fixture
def clean_fichiers(request):
    def finalizer():
        db.fichiers.remove()
    request.addfinalizer(finalizer)


@pytest.fixture
def file_init(clean_fichiers, observateur):
    r = observateur.post('/fichiers', json={'titre': 'test.png'})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def file_bad_name(observateur):
    bad_titres = ['', '*', '../test', 'éééé']
    for titre in bad_titres:
        r = observateur.post('/fichiers', json={'titre': titre})
        assert r.status_code == 422, r.text


@pytest.fixture
def file_uploaded(clean_fichiers, observateur):
    r = observateur.post('/fichiers', json={'titre': 'test.png'})
    assert r.status_code == 201, r.text
    r = observateur.post('/fichiers/' + r.json()['_id'])
    assert r.status_code == 200, r.text
    return r.json()


def custom_upload_file(payload, user, upload_done=True):
    r = user.post('/fichiers', json=payload)
    assert r.status_code == 201, r.text
    if upload_done:
        r = user.post('/fichiers/' + r.json()['_id'])
        assert r.status_code == 200, r.text
    return r.json()


def test_singlepart_upload(clean_fichiers, observateur):
    # First declare the file to get a signed request url
    r = observateur.post('/fichiers', json={'titre': 'test.png'})
    assert r.status_code == 201, r.text
    response = r.json()
    assert 's3_signed_url' in response
    assert response['mime'] == 'image/png'
    # We should be uploading to S3 here...
    # Once the upload is done, we have to signify it to the server
    r = observateur.post('/fichiers/' + response['_id'])
    assert r.status_code == 200, r.text
    assert 'disponible' in r.json()
    assert r.json()['disponible']


@pytest.mark.xfail(reason='multipart is no longer supported')
def test_multipart_upload(clean_fichiers, observateur):
    # First declare the file to get a signed request url
    r = observateur.post('/fichiers',
        json={'titre': 'test.png', 'multipart': True})
    assert r.status_code == 201, r.text
    response = r.json()
    assert 's3_upload_multipart_id' in response
    assert response['mime'] == 'image/png'
    # Request part upload signed url
    fichier_url = '/fichiers/' + response['_id']
    r = observateur.put(fichier_url + '/multipart',
                        json={'part_number': 1})
    assert r.status_code == 200, r.text
    assert 's3_signed_url' in r.json()
    # We should be uploading to S3 here...
    # Once the upload is done, we have to signify it to the server
    r = observateur.post(fichier_url,
                         json={'parts': [{'part_number': 1, 'etag': uuid4().hex}]})
    assert r.status_code == 200, r.text
    assert 'disponible' in r.json()
    assert r.json()['disponible']


def test_access(file_init, observateur):
    # Cannot acces unfinished file
    url = '/fichiers/' + file_init['_id']
    url_s3_access = url + '/acces'
    r = observateur.get(url_s3_access)
    assert r.status_code == 410, r.text
    # Finish the upload and retry to access the file
    r = observateur.post('/fichiers/' + file_init['_id'])
    assert r.status_code == 200, r.text
    r = observateur.get(url_s3_access)
    assert r.status_code == 200, r.text
    assert 's3_signed_url' in r.json()
    # Test the redirection too
    r = observateur.get(url_s3_access, params={'redirection': True},
                        allow_redirects=False)
    assert r.status_code == 302, r.text


def test_access_rights(file_uploaded, observateur, observateur_other,
                       validateur, administrateur):
    # Default is other users can access uploaded files
    url = '/fichiers/' + file_uploaded['_id']
    url_s3_access = url + '/acces'
    r = validateur.get(url)
    assert r.status_code == 200, r.text
    r = validateur.get(url_s3_access)
    assert r.status_code == 200, r.text
    assert 's3_signed_url' in r.json()
    # Switch to private file
    r = administrateur.patch(observateur.url,
                          headers={'If-Match': observateur.user['_etag']},
                          json={'donnees_publiques': False})
    assert r.status_code == 200, r.text
    def try_access(user, result):
        r = user.get(url)
        assert r.status_code == result, r.text
        r = user.get(url_s3_access)
        assert r.status_code == result, r.text
        if result == 200:
            assert 's3_signed_url' in r.json()
        # Test redirection mode too
        r = user.get(url_s3_access, params={'redirection': True},
                     allow_redirects=False)
        if result == 200:
            assert r.status_code == 302, r.text
        else:
            assert r.status_code == result, r.text
    # Now access is forbidden for all observateurs except owner,
    # admin and validateur have still access
    try_access(observateur_other, 403)
    try_access(observateur, 200)
    try_access(validateur, 200)
    try_access(administrateur, 200)


def test_not_loggedin(file_uploaded):
    url_s3_access = '{}/fichiers/{}/acces'.format(
        settings.BACKEND_DOMAIN, file_uploaded['_id'])
    r = requests.get(url_s3_access)
    assert r.status_code == 401, r.text


def test_same_file_name(clean_fichiers, obs_sites_base):
    observateur, sites = obs_sites_base
    json_payload = {'titre': 'test.png'}
    # First declare the file to get a signed request url
    r = observateur.post('/fichiers', json=json_payload)
    assert r.status_code == 201, r.text
    response = r.json()
    # Try to re-upload the same is allowed because the upload
    # is not flagged as finished
    r = observateur.post('/fichiers', json=json_payload)
    assert r.status_code == 201, r.text
    # We should be uploading to S3 here...
    # Once the upload is done, we have to signify it to the server
    r = observateur.post('/fichiers/' + response['_id'])
    assert r.status_code == 200, r.text
    # Now we are no longer allowed to upload with the same file
    r = observateur.post('/fichiers', json=json_payload)
    assert r.status_code == 409, r.text

    participations_url = '/sites/{}/participations'.format(sites[0]['_id'])
    r = observateur.post(participations_url,
                         json={'date_debut': format_datetime(datetime.utcnow())})
    assert r.status_code == 201, r.text
    participation1 = r.json()
    r = observateur.post(participations_url,
                         json={'date_debut': format_datetime(datetime.utcnow())})
    assert r.status_code == 201, r.text
    participation2 = r.json()

    # Same thing within the same participation
    json_payload = {'titre': 'test2.png', 'lien_participation': participation1['_id']}
    r = observateur.post('/fichiers', json=json_payload)
    assert r.status_code == 201, r.text
    response = r.json()
    r = observateur.post('/fichiers/' + response['_id'])
    assert r.status_code == 200, r.text
    r = observateur.post('/fichiers', json=json_payload)
    assert r.status_code == 409, r.text

    # Same name in different participation is allowed
    json_payload["lien_participation"] = participation2['_id']
    r = observateur.post('/fichiers', json=json_payload)
    assert r.status_code == 201, r.text
