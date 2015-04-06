import os
import pytest
import requests
from pymongo import MongoClient
from bson import ObjectId

from vigiechiro import settings
from vigiechiro.scripts import tadaridaC

from .test_fake_s3 import fake_s3, TAS_DEFAULT_DIR

AUTH = (settings.SCRIPT_WORKER_TOKEN, None)
# To save complexity, just hack into the database the only needed
# informations (i.e. the fichier and donnee) instead of creating an
# observateur, join a protocole, then create a site, etc...
db = MongoClient(host=settings.get_mongo_uri())[settings.MONGO_DBNAME]


@pytest.fixture
def init_env(fake_s3, request):
    fichiers_ids = []
    donnees_ids = []
    default_tas = sorted([n for n in os.listdir(TAS_DEFAULT_DIR)
                            if n.rsplit('.', 1)[-1] == 'ta'])
    for ta in default_tas:
        # First upload the ta in the backend and in S3
        fichiers_url = settings.BACKEND_DOMAIN + '/fichiers'
        r = requests.post(fichiers_url, auth=AUTH,
                          json={'titre': ta, 'mime': 'application/ta'})
        assert r.status_code == 201, r.text
        path = TAS_DEFAULT_DIR + '/' + ta
        fichier_id = ObjectId(r.json()['_id'])
        r = requests.post(r.json()['s3_signed_url'],
                          files={'file': open(path, 'rb')})
        assert r.status_code == 200, r.text
        r = requests.post(fichiers_url + '/' + str(fichier_id), auth=AUTH)
        assert r.status_code == 200, r.text
        # Now create a corresponding empty donnee
        donnee_id = db.donnees.insert({})
        db.fichiers.update({'_id': fichier_id}, {'$set': {'lien_donnee': donnee_id}})
        donnees_ids.append(donnee_id)
        fichiers_ids.append(fichier_id)
    def finalizer():
        db.donnees.remove({'_id': {'$in': donnees_ids}})
        db.fichiers.remove({'_id': {'$in': fichiers_ids}})
    request.addfinalizer(finalizer)
    return list(zip(fichiers_ids, donnees_ids))


@pytest.mark.slow
def test_tadaridaC(init_env):
    # Run tadaridaD on each fichier
    for fichier_id, donnee_id in init_env:
        assert tadaridaC(str(fichier_id)) == 0
        fichiers = db.fichiers.find({'lien_donnee': donnee_id})
        assert fichiers.count() == 2, list(fichiers)
        fichier_ta = next((f for f in fichiers if f['mime'] == 'application/ta'), None)
        fichier_tc = next((f for f in fichiers if f['mime'] == 'application/tc'), None)
        assert fichier_ta
        assert fichier_tc
        assert (fichier_ta['titre'].rsplit('.', 1)[0] ==
                fichier_tc['titre'].rsplit('.', 1)[0])
        # TODO check observations in donnee
        donnee = db.donnees.find_one(donnee_id)
        assert donnee
