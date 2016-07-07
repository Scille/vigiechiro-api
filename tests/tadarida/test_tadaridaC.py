import os
import pytest
import requests
from pymongo import MongoClient
from bson import ObjectId
from uuid import uuid4

from vigiechiro import settings

from .test_fake_s3 import fake_s3, TAS_DEFAULT_DIR

AUTH = (settings.SCRIPT_WORKER_TOKEN, None)
# To save complexity, just hack into the database the only needed
# informations (i.e. the fichier and donnee) instead of creating an
# observateur, join a protocole, then create a site, etc...
db = MongoClient(host=settings.MONGO_HOST).get_default_database()


@pytest.fixture
def taxons(request):
    ids = []
    for taxon in ["Antius", "Antped", "Antsor", "Aposyl", "Barbar", "Barsan",
                  "Cansp.", "Cicorn", "Confus", "criq", "Cympud", "Cyrscu",
                  "Decalb", "Epheph", "Eptser", "Eumbor", "Eupcha", "Hypsav",
                  "Inssp1", "Inssp2", "Inssp5", "Lepbos", "Leppun", "mamm",
                  "Metroe", "Micagr", "Minsch", "Mussp", "Myoalc", "Myobec",
                  "Myocap", "Myodau", "Myoema", "MyoGT", "Myomys", "Myonat",
                  "noise", "Nyclas", "Nyclei", "Nycnoc", "Phafal", "Phanan",
                  "Phofem", "Phogri", "piaf", "Pipkuh", "Pipnat", "Pippip",
                  "Pippyg", "Plaaff", "Plaalb", "Plafal", "Plaint", "Plasab",
                  "Pleaur", "Pleaus", "Plemac", "Poepal", "Pteger", "Ptepon",
                  "Ratnor", "Rhieur", "Rhifer", "Rhihip", "Rusnit", "Sepsep",
                  "Tadten", "Testes", "Tetarg", "Tetpyg", "Tetvir", "Thycor",
                  "Tyllil", "Urorug", "Vesmur", "Yerray", "Zeuabb"]:
        r = requests.post('{}/taxons'.format(settings.BACKEND_DOMAIN),
                          json={'libelle_court': taxon, 'libelle_long': taxon},
                          auth=AUTH)
        assert r.status_code == 201, r.text
        ids.append(r.json()['_id'])
    def finalizer():
        db.taxons.remove({'_id': {'$in': ids}})
    request.addfinalizer(finalizer)
    return ids


@pytest.fixture
def init_env(taxons, fake_s3, request):
    r = requests.get('{}/moi'.format(settings.BACKEND_DOMAIN), auth=AUTH)
    assert r.status_code == 200, r.text
    my_id = r.json()['_id']
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
        participation_id = db.participations.insert({})
        donnee_id = db.donnees.insert({'_etag': uuid4().hex, 'proprietaire': ObjectId(my_id),
                                       'participation': participation_id})
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
@pytest.mark.rtest
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
        assert 'observations' in donnee
