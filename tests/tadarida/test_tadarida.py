import logging; logging.basicConfig(level=logging.INFO)

import os
import re
import pytest
import shutil
import requests
import tempfile
from bson import ObjectId
from multiprocessing import Process
from datetime import datetime

from vigiechiro.scripts import tadarida

from ..common import (db, observateur, observateur_other, validateur,
                     administrateur, format_datetime, with_flask_context)
from ..test_participation import participation_ready, clean_participations
from ..test_protocoles import protocoles_base
from ..test_taxons import taxons_base
from ..test_sites import obs_sites_base
from ..test_fichiers import (file_uploaded, custom_upload_file, clean_fichiers,
                             file_init, file_uploaded)

from .test_fake_s3 import fake_s3, S3_ADDRESS, WAVES_DEFAULT_DIR, TAS_DEFAULT_DIR


def _generate_participation(pieces_jointes, participation_ready):
    observateur, protocole, site = participation_ready
    # First, upload some fichiers
    fichiers_ids = []
    for pj in pieces_jointes:
        pj_json = pj.copy()
        pj_path = pj_json.pop('path')
        pj_type = pj_json.pop('type')
        # First register the file in the backend
        r = observateur.post('/fichiers', json=pj_json)
        assert r.status_code == 201, r.text
        pj_id = r.json()['_id']
        # pjs_participation = {}
        # if pj_type not in pjs_participation:
        #     pjs_participation[pj_type] = []
        # pjs_participation[pj_type].append(pj_id)
        # Then post it to s3 with the signed url
        r = requests.post(r.json()['s3_signed_url'],
                          files={'file': open(pj_path, 'rb')})
        assert r.status_code == 200, r.text
        # Finally notify the upload to the backend
        r = observateur.post('/fichiers/' + pj_id)
        assert r.status_code == 200, r.text
        fichiers_ids.append(pj_id)
    # Now post participation with the fichiers to let the backend generate the donnees
    participations_url = '/sites/{}/participations'.format(site['_id'])
    r = observateur.post(participations_url,
                         json={'date_debut': format_datetime(datetime.utcnow()),
                               'donnees': fichiers_ids})
    assert r.status_code == 201, r.text
    participation = r.json()
    return  participation, fichiers_ids
    # # Upload files
    # pjs_participation = {}
    # pieces_jointes_url = '/participations/{}/pieces_jointes'.format(participation['_id'])
    # # Mark files as part of the participation
    # r = observateur.put(pieces_jointes_url, json=pjs_participation)
    # assert r.status_code == 200, r.text
    # return participation, pjs_participation


@pytest.mark.slow
def test_tadaridaD(fake_s3, clean_fichiers, participation_ready):
    files = [{'path': WAVES_DEFAULT_DIR + '/' + t, 'titre': t,
              'mime': 'audio/wav', 'type': 'wav'}
             for t in os.listdir(WAVES_DEFAULT_DIR)]
    participation, fichiers_ids = _generate_participation(files, participation_ready)
    # Now we have a participation with some wav files associated and requesting
    # a tadaridaD processing, it's time to actually release tadaridaD !
    tadarida.run_tadarida_d()
    # Finally check the result of tadarida
    for f_id in fichiers_ids:
        f_id = ObjectId(f_id)
        # Each wav should have been processed and then have a corresponding ta
        f_obj = db.fichiers.find_one({'_id': f_id})
        assert f_obj
        assert not f_obj.get('require_process', None)
        # Retrieve the donnee linked to this fichiers
        d_ids = f_obj['lien_donnee']
        d_obj = db.donnees.find_one({'_id': d_ids})
        assert d_obj
        # From the donnee, get all the fichiers
        d_fichiers = db.fichiers.find({'lien_donnee': d_ids})
        # Should have the original .wav and the generated .ta
        assert d_fichiers.count() == 2
        assert next((f for f in d_fichiers if f['_id'] == f_id), None)
        ta_f_obj = next((f for f in d_fichiers if f['_id'] != f_id), None)
        assert ta_f_obj, d_fichiers
        assert ta_f_obj['mime'] in ['application/ta', 'application/tac']
        assert (ta_f_obj.get('lien_donnee', None) ==
                f_obj.get('lien_donnee', None))
        assert ta_f_obj.get('require_process', None) == 'tadarida_c'
        assert ta_f_obj['proprietaire'] == f_obj['proprietaire']


@pytest.mark.slow
def test_tadaridaC(fake_s3, clean_fichiers, participation_ready):
    files = [{'path': TAS_DEFAULT_DIR + '/' + t, 'titre': t,
              'mime': 'application/ta', 'type': 'ta'}
             for t in os.listdir(TAS_DEFAULT_DIR)]
    participation, fichiers_ids = _generate_participation(files, participation_ready)
    # Now we have a participation with some ta files associated and requesting
    # a tadaridaD processing, it's time to actually release tadaridaD !
    tadarida.run_tadarida_c()
    # Finally check the result of tadarida
    for f_id in fichiers_ids:
        f_id = ObjectId(f_id)
        # Each ta should have been processed and then have a corresponding tc
        f_ta_obj = db.fichiers.find_one({'_id': f_id})
        assert f_ta_obj
        assert not f_ta_obj.get('require_process', None)
        # Retrieve the donnee linked to this fichiers
        d_ids = f_ta_obj['lien_donnee']
        d_obj = db.donnees.find_one({'_id': d_ids})
        assert d_obj
        f_tc_objs = db.fichiers.find({'lien_donnee': d_ids})
        # Should have the original .ta and the generated .tc
        assert f_tc_objs.count() == 2
        assert next((f for f in f_tc_objs if f['_id'] == f_id), None)
        f_tc_obj = next((f for f in f_tc_objs if f['_id'] != f_id), None)
        assert f_tc_obj['mime'] in ['application/tc', 'application/tcc']
        assert (f_tc_obj.get('lien_donnee', None) ==
                f_ta_obj.get('lien_donnee', None))
        assert f_tc_obj.get('require_process', None) == None
        assert f_tc_obj['proprietaire'] == f_ta_obj['proprietaire']
