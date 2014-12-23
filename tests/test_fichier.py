import requests
from pymongo import MongoClient
import pytest

from common import db, administrateur, validateur, observateur, eve_post_internal


def test_upload(observateur):
    # First declare the file to get a signed request url
    r = observateur.post('/fichiers/s3', json={'mime': 'image/png'})
    assert r.status_code == 201, r.text
    response = r.json()
    assert 'signed_request' in response
    # We should be uploading to S3 here...
    # Once the upload is done, we have to signify it to the server
    r = observateur.patch('/fichiers/' + response['_id'],
                          headers={'If-Match': response['_etag']},
                          json={'upload_realise': True})
    assert r.status_code == 200, r.text


def test_access_rights(observateur, validateur, administrateur):
    r = observateur.post('/fichiers/s3', json={'mime': 'image/png'})
    assert r.status_code == 201, r.text
    response = r.json()
    # Default is other users can access uploaded files
    url = '/fichiers/' + response['_id']
    url_s3_access = url + '/action/acces'
    r = validateur.get(url)
    assert r.status_code == 200, r.text
    r = validateur.get(url_s3_access, allow_redirects=False)
    assert r.status_code == 302, r.text
    r = observateur.patch(url, headers={'If-Match': response['_etag']},
                          json={'prive': True})
    assert r.status_code == 200, r.text
    r = observateur.get(url)
    assert r.status_code == 200 and r.json()['prive'], r.text
    # Now access is only for myself...
    r = validateur.get(url)
    assert r.status_code == 403, r.text
    r = validateur.get(url_s3_access, allow_redirects=False)
    assert r.status_code == 403, r.text
    r = observateur.get(url)
    assert r.status_code == 200, r.text
    r = observateur.get(url_s3_access, allow_redirects=False)
    assert r.status_code == 302, r.text
    # ...but admin is still admin !
    r = administrateur.get(url)
    assert r.status_code == 200, r.text
    r = administrateur.get(url_s3_access, allow_redirects=False)
    assert r.status_code == 302, r.text
