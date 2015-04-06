#! /usr/bin/env python3

"""
Tadarida-D task worker
"""

import logging; logging.basicConfig(level=logging.INFO)
import sys
import os
import tempfile
import subprocess
import requests
from celery import Celery

from .. import settings

TADARIDA_D = os.path.abspath(os.path.dirname(__file__)) + '/../../bin/tadaridaD'
TADARIDA_C = os.path.abspath(os.path.dirname(__file__)) + '/../../bin/tadaridaC'
BACKEND_DOMAIN = settings.BACKEND_DOMAIN
AUTH = (settings.SCRIPT_WORKER_TOKEN, None)
CELERY_BROKER_URL = settings.CELERY_BROKER_URL
ALLOWED_MIMES_WAV = ['audio/wav', 'audio/x-wav']

app = Celery('tasks', broker=CELERY_BROKER_URL)


def _create_working_dir(subdirs):
    wdir  = tempfile.mkdtemp()
    logging.info('working in directory {}'.format(wdir))
    for subdir in subdirs:
        os.mkdir(wdir + '/' + subdir)
    return wdir


@app.task
def tadaridaD(fichier_id):
    wdir_path = _create_working_dir(['waves'])
    # Retreive the fichier resource
    r = requests.get(BACKEND_DOMAIN + '/fichiers/' + fichier_id, auth=AUTH)
    if r.status_code != 200:
        logging.error('Cannot retreive fichier {}'.format(fichier_id))
        return 1
    fichier = r.json()
    fichier_info = '{} ({})'.format(fichier['_id'], fichier['titre'])
    if fichier['mime'] not in ALLOWED_MIMES_WAV:
        logging.error('Fichier {} is not a wav file (mime: {})'.format(
            fichier_info, fichier['mime']))
        return 1
    if 'lien_donnee' not in fichier:
        logging.error('{} must have a lien_donnee in order to link '
                      'the generated .ta to something'.format(fichier_info))
        return 1
    # Download the file
    logging.info('Downloading file {}'.format(fichier_info))
    r = requests.get('{}/fichiers/{}/acces'.format(BACKEND_DOMAIN, fichier_id),
        params={'redirection': True}, stream=True, auth=AUTH)
    # Make sure to give wav file a .wav extension (needed by tadaridaD)
    input_path = wdir_path + '/waves/' + fichier['titre'].rsplit('.', 1)[0] + '.wav'
    with open(input_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024): 
            if chunk: # filter out keep-alive new chunks
                f.write(chunk)
                f.flush()
    if r.status_code != 200:
        logging.error('Cannot get back file {} : {}, {}'.format(
            fichier_info, r.status_code, r.text))
        return 1
    logging.info('Got back file {}, running tadaridaD on it'.format(fichier_info))
    # Run tadarida
    ret = subprocess.call([TADARIDA_D, 'waves'], cwd=wdir_path)
    if ret:
        logging.error('Error in running tadaridaD : returns {}'.format(ret))
        return 1
    # A .ta file should have been generated
    output_path = wdir_path + '/waves/txt/' + fichier['titre'].rsplit('.', 1)[0] + '.ta'
    output_name = output_path.split('/')[-1]
    if not os.path.exists(output_path):
        logging.warning("{} hasn't been created, hence {} has"
                        " not been processed".format(
                            output_name, fichier_info))
        return 1
    # Add the .ta as a fichier in the backend and upload it to S3
    ta_payload = {'titre': output_name,
                  'mime': 'application/ta',
                  'proprietaire': str(fichier['proprietaire']),
                  'lien_donnee': str(fichier['lien_donnee'])}
    r = requests.post(BACKEND_DOMAIN + '/fichiers', json=ta_payload, auth=AUTH)
    if r.status_code != 201:
        logging.error("{}'s .ta backend post {} error {} : {}".format(
            fichier_info, ta_payload, r.status_code, r.text))
        return 1
    ta_data = r.json()
    ta_fichier_info = '{} ({})'.format(ta_data['_id'], ta_data['titre'])
    logging.info("Registered {}'s .ta as {}".format(fichier_info, ta_fichier_info))
    # Then post it to s3 with the signed url
    s3_signed_url = ta_data['s3_signed_url']
    r = requests.post(s3_signed_url,
                      files={'file': open(output_path, 'rb')})
    if r.status_code != 200:
        logging.error('post to s3 {} error {} : {}'.format(s3_signed_url, r.status_code, r.text))
        return 1
    # Notify the upload to the backend
    r = requests.post(BACKEND_DOMAIN + '/fichiers/' + ta_data['_id'], auth=AUTH)
    if r.status_code != 200:
        logging.error('Notify end upload for {} error {} : {}'.format(
            ta_data['_id'], r.status_code, r.text))
        return 1
    return 0
