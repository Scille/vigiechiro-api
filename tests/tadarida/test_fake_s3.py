import os
import re
import pytest
import time
import shutil
import requests
import tempfile
from multiprocessing import Process
from datetime import datetime

from ..common import (db, observateur, observateur_other, validateur,
                     administrateur, format_datetime, with_flask_context)
from ..test_participation import participation_ready, clean_participations
from ..test_protocoles import protocoles_base
from ..test_taxons import taxons_base
from ..test_sites import obs_sites_base
from ..test_fichiers import (file_uploaded, custom_upload_file, clean_fichiers,
                             file_init, file_uploaded)

from .fake_s3 import start_server


S3_ADDRESS = 'http://localhost:8000'
WAVES_DEFAULT_DIR = os.path.abspath(os.path.dirname(__file__)) + '/default_waves'
TAS_DEFAULT_DIR = os.path.abspath(os.path.dirname(__file__)) + '/default_tas'


@pytest.fixture
def fake_s3(request):
    # Run the fake s3 in a temp dir
    wdir  = tempfile.mkdtemp()
    print('Fake S3 directory : {}'.format(wdir))
    # shutil.copytree(S3_INIT_DIR, s3_work_dir)
    # Switch to create directory and start server
    os.chdir(wdir)
    p = Process(target=start_server)
    p.start()
    def finalizer():
        print('Terminating fake s3...', flush=True, end='')
        p.terminate()
        p.join()
        shutil.rmtree(wdir)
        print(' Done !')
    request.addfinalizer(finalizer)
    # Wait for server ready
    while True:
        try:
            ret = requests.get(S3_ADDRESS)
            assert ret.ok
            break
        except requests.exceptions.ConnectionError:
            time.sleep(0.1)
    return wdir


def test_fake_s3(fake_s3, clean_fichiers):
    default_waves = sorted(os.listdir(WAVES_DEFAULT_DIR))
    # Test post file
    wav_0_name = default_waves[0]
    with open(WAVES_DEFAULT_DIR + '/' + wav_0_name, 'rb') as fd:
        wav_0_data = fd.read()
    r = requests.post(S3_ADDRESS + '/' + wav_0_name,
                      files={'file': (wav_0_name, wav_0_data)})
    assert r.status_code == 200, r.text
    # We must create the subdir first
    os.mkdir(fake_s3 + '/sub')
    # Test post in subdir using key header
    wav_1_name = default_waves[1]
    r = requests.post(S3_ADDRESS + '/sub',
        files={'file': open(WAVES_DEFAULT_DIR + '/' + wav_1_name, 'rb')},
        headers={'key': '/sub/${filename}'})
    assert r.status_code == 200, r.text
    # Test post in subdir using path route
    wav_2_name = default_waves[2]
    r = requests.post(S3_ADDRESS + '/sub/' + wav_2_name,
        files={'file': open(WAVES_DEFAULT_DIR + '/' + wav_2_name, 'rb')})
    assert r.status_code == 200, r.text
    # Test get root
    r = requests.get(S3_ADDRESS)
    assert r.status_code == 200, r.text
    ls = sorted(re.findall(r'<li><a href="(.*)">', r.text))
    assert ls == sorted([wav_0_name, 'sub/'])
    # Test get file
    r = requests.get(S3_ADDRESS + '/' + wav_0_name)
    assert r.status_code == 200, r.text
    assert r.content == wav_0_data
    # Test get subdir
    r = requests.get(S3_ADDRESS + '/sub')
    assert r.status_code == 200, r.text
    ls = sorted(re.findall(r'<li><a href="(.*)">', r.text))
    assert ls == sorted([wav_1_name, wav_2_name])


def test_participation(fake_s3, clean_fichiers, participation_ready):
    observateur, protocole, site = participation_ready
    # Post participation
    participations_url = '/sites/{}/participations'.format(site['_id'])
    r = observateur.post(participations_url,
                         json={'date_debut': format_datetime(datetime.utcnow())})
    assert r.status_code == 201, r.text
    participation = r.json()
    sent_pieces_jointes = set()
    # Upload files
    waves = [{'title': t} for t in sorted(os.listdir(WAVES_DEFAULT_DIR))]
    pieces_jointes_url = '/participations/{}/pieces_jointes'.format(participation['_id'])
    for wav in waves:
        title = wav['title']
        # First register the file in the backend
        r = observateur.post('/fichiers', json={'titre': title})
        assert r.status_code == 201, r.text
        wav['data'] = r.json()
        # Then post it to s3 with the signed url
        r = requests.post(wav['data']['s3_signed_url'],
                          files={'file': open(WAVES_DEFAULT_DIR + '/' + title, 'rb')})
        assert r.status_code == 200, r.text
        # Finally notify the upload to the backend
        r = observateur.post('/fichiers/' + wav['data']['_id'])
        assert r.status_code == 200, r.text
    # Mark files as part of the participation
    r = observateur.put(pieces_jointes_url,
                        json={'wav': [wav['data']['_id'] for wav in waves]})
    # Make sure we can access the files
    for wav in waves:
        print('/fichiers/' + wav['data']['_id'] + '/acces')
        r = observateur.get('/fichiers/' + wav['data']['_id'] + '/acces', params={'redirection': True})
        assert r.status_code == 200, r.text
        with open(WAVES_DEFAULT_DIR + '/' + wav['title'], 'rb') as fd:
            assert r.content == fd.read()
