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
    # Post participation
    participations_url = '/sites/{}/participations'.format(site['_id'])
    r = observateur.post(participations_url,
                         json={'date_debut': format_datetime(datetime.utcnow())})
    assert r.status_code == 201, r.text
    participation = r.json()
    # Upload files
    pjs_participation = {}
    pieces_jointes_url = '/participations/{}/pieces_jointes'.format(participation['_id'])
    for pj in pieces_jointes:
        pj_json = pj.copy()
        pj_path = pj_json.pop('path')
        pj_type = pj_json.pop('type')
        # First register the file in the backend
        r = observateur.post('/fichiers', json=pj_json)
        assert r.status_code == 201, r.text
        pj_id = r.json()['_id']
        if pj_type not in pjs_participation:
            pjs_participation[pj_type] = []
        pjs_participation[pj_type].append(pj_id)
        # Then post it to s3 with the signed url
        r = requests.post(r.json()['s3_signed_url'],
                          files={'file': open(pj_path, 'rb')})
        assert r.status_code == 200, r.text
        # Finally notify the upload to the backend
        r = observateur.post('/fichiers/' + pj_id)
        assert r.status_code == 200, r.text
    # Mark files as part of the participation
    r = observateur.put(pieces_jointes_url, json=pjs_participation)
    assert r.status_code == 200, r.text
    return participation, pjs_participation


def test_tadaridaD(fake_s3, clean_fichiers, participation_ready):
    files = [{'path': WAVES_DEFAULT_DIR + '/' + t, 'titre': t,
              'mime': 'audio/wav', 'type': 'wav'}
             for t in os.listdir(WAVES_DEFAULT_DIR)]
    participation, pjs_participation = _generate_participation(files, participation_ready)
    # Now we have a participation with some wav files associated and requesting
    # a tadaridaD processing, it's time to actually release tadaridaD !
    tadarida.run_tadarida_d()
    # Finally check the result of tadarida
    for pj in pjs_participation['wav']:
        # Each wav should have been processed and then have a corresponding ta
        pj_obj = db.fichiers.find_one({'_id': ObjectId(pj)})
        assert pj_obj
        assert not pj_obj.get('require_process', None)
        pj_ta_objs = db.fichiers.find({'fichier_source': pj_obj['_id']})
        assert pj_ta_objs.count() == 1
        pj_ta_obj = pj_ta_objs[0]
        assert pj_ta_obj['mime'] in ['application/ta', 'application/tac']
        assert (pj_ta_obj.get('lien_participation', None) ==
                pj_obj.get('lien_participation', None))
        assert pj_ta_obj.get('require_process', None) == 'tadarida_c'
        assert pj_ta_obj['proprietaire'] == pj_obj['proprietaire']


def test_tadaridaC(fake_s3, clean_fichiers, participation_ready):
    files = [{'path': TAS_DEFAULT_DIR + '/' + t, 'titre': t,
              'mime': 'application/ta', 'type': 'ta'}
             for t in os.listdir(TAS_DEFAULT_DIR)]
    participation, pjs_participation = _generate_participation(files, participation_ready)
    # Now we have a participation with some wav files associated and requesting
    # a tadaridaD processing, it's time to actually release tadaridaD !
    tadarida.run_tadarida_c()
    # Finally check the result of tadarida
    for pj in pjs_participation['ta']:
        # Each wav should have been processed and then have a corresponding ta
        pj_ta_obj = db.fichiers.find_one({'_id': ObjectId(pj)})
        assert pj_ta_obj
        assert not pj_ta_obj.get('require_process', None)
        pj_tc_objs = db.fichiers.find({'fichier_source': pj_ta_obj['_id']})
        assert pj_tc_objs.count() == 1
        pj_tc_obj = pj_tc_objs[0]
        assert pj_tc_obj['mime'] in ['application/tc', 'application/tcc']
        assert (pj_tc_obj.get('lien_participation', None) ==
                pj_ta_obj.get('lien_participation', None))
        assert pj_tc_obj.get('require_process', None) == None
        assert pj_tc_obj['proprietaire'] == pj_ta_obj['proprietaire']
