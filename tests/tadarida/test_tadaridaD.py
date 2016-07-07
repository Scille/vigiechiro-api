import os
import pytest
import requests
from pymongo import MongoClient
from bson import ObjectId
from uuid import uuid4

from vigiechiro import settings

from .test_fake_s3 import fake_s3, S3_ADDRESS, WAVES_DEFAULT_DIR

AUTH = (settings.SCRIPT_WORKER_TOKEN, None)
# To save complexity, just hack into the database the only needed
# informations (i.e. the fichier and donnee) instead of creating an
# observateur, join a protocole, then create a site, etc...
db = MongoClient(host=settings.MONGO_HOST).get_default_database()


@pytest.fixture
def init_env(fake_s3, request):
    r = requests.get('{}/moi'.format(settings.BACKEND_DOMAIN), auth=AUTH)
    assert r.status_code == 200, r.text
    my_id = r.json()['_id']
    fichiers_ids = []
    donnees_ids = []
    default_waves = sorted([n for n in os.listdir(WAVES_DEFAULT_DIR)
                            if n.rsplit('.', 1)[-1] == 'wav'])
    for wav in default_waves:
        # First upload the wav in the backend and in S3
        fichiers_url = settings.BACKEND_DOMAIN + '/fichiers'
        r = requests.post(fichiers_url, auth=AUTH,
                          json={'titre': wav, 'mime': 'audio/wav'})
        assert r.status_code == 201, r.text
        path = WAVES_DEFAULT_DIR + '/' + wav
        fichier_id = ObjectId(r.json()['_id'])
        r = requests.post(r.json()['s3_signed_url'],
                          files={'file': open(path, 'rb')})
        assert r.status_code == 200, r.text
        r = requests.post(fichiers_url + '/' + str(fichier_id), auth=AUTH)
        assert r.status_code == 200, r.text
        # Now create a corresponding empty donnee
        donnee_id = db.donnees.insert({'_etag': uuid4().hex, 'proprietaire': ObjectId(my_id)})
        db.fichiers.update({'_id': fichier_id}, {'$set': {'lien_donnee': donnee_id}})
        donnees_ids.append(donnee_id)
        fichiers_ids.append(fichier_id)
    def finalizer():
        db.donnees.remove({'_id': {'$in': donnees_ids}})
        db.fichiers.remove({'_id': {'$in': fichiers_ids}})
    request.addfinalizer(finalizer)
    return list(zip(fichiers_ids, donnees_ids))


@pytest.mark.xfail
@pytest.mark.slow
def test_tadaridaD(init_env):
    # Run tadaridaD on each fichier
    for fichier_id, donnee_id in init_env:
        assert tadaridaD(str(fichier_id)) == 0
        fichiers = db.fichiers.find({'lien_donnee': donnee_id})
        assert fichiers.count() == 2, list(fichiers)
        fichier_wav = next((f for f in fichiers if f['mime'] == 'audio/wav'), None)
        fichier_ta = next((f for f in fichiers if f['mime'] == 'application/ta'), None)
        assert fichier_ta
        assert fichier_wav
        assert (fichier_ta['titre'].rsplit('.', 1)[0] ==
                fichier_wav['titre'].rsplit('.', 1)[0])
