import requests
from pymongo import MongoClient
import pytest

from common import db, administrateur, validateur, observateur, observateur_other
from vigiechiro import settings
from vigiechiro.resources import fichiers as fichiers_resource


@pytest.fixture
def clean_fichiers(request):
    def finalizer():
        db.fichiers.remove()
    request.addfinalizer(finalizer)


@pytest.fixture
def file_init(clean_fichiers, observateur):
    r = observateur.post('/fichiers', json={'titre': 'test', 'mime': 'image/png'})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def file_uploaded(clean_fichiers, observateur):
    r = observateur.post('/fichiers', json={'titre': 'test', 'mime': 'image/png'})
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
    r = observateur.post('/fichiers', json={'titre': 'test', 'mime': 'image/png'})
    assert r.status_code == 201, r.text
    response = r.json()
    assert 's3_signed_url' in response
    # We should be uploading to S3 here...
    # Once the upload is done, we have to signify it to the server
    r = observateur.post('/fichiers/' + response['_id'])
    assert r.status_code == 200, r.text
    assert 's3_upload_done' in r.json()
    assert r.json()['s3_upload_done']

@pytest.mark.xfail
def test_multipart_upload(clean_fichiers, observateur):
    # First declare the file to get a signed request url
    r = observateur.post('/fichiers',
        json={'titre': 'test', 'mime': 'image/png', 'multipart': True})
    assert r.status_code == 201, r.text
    response = r.json()
    assert 's3_multipart_upload_id' in response
    assert 's3_signed_url' in response
    # We should be uploading to S3 here...
    # Once the upload is done, we have to signify it to the server
    r = observateur.post('/fichiers/' + response['_id'])
    assert r.status_code == 200, r.text
    assert 's3_upload_done' in r.json()
    assert r.json()['s3_upload_done']


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
    r = observateur.patch('/moi',
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