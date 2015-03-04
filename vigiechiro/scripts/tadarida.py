import os
import logging
import tempfile
import requests
import bson
import subprocess
from pymongo import MongoClient

from .celery import celery_app
from .. import settings


TADARIDA_D = os.path.abspath(os.path.dirname(__file__)) + '/../../bin/tadaridaD'
logging.info('tadaridaD is {}'.format(TADARIDA_D))


class S3Error(Exception): pass


def _download_files(wdir_path, to_compute):
    for file_resource in to_compute:
        file_info = '{} ({})'.format(file_resource['_id'], file_resource['titre'])
        r = requests.get(
            '{}/fichiers/{}/acces'.format(settings.BACKEND_DOMAIN, file_resource['_id']),
            params={'redirection': True}, stream=True, auth=(settings.SECRET_KEY, None))
        local_filename = wdir_path + '/waves/' + file_info['titre']
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024): 
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)
                    f.flush()
        if r.status_code != 200:
            raise S3Error('Cannot get back file {} : {}, {}'.format(
                file_info, r.status_code, r.text))
        logging.info('got back file {}'.format(file_info))


def _upload_results(wdir_path):
    if not os.path.exists(wdir_path + '/waves/txt'):
        logging.warning("txt output directory hasn't been created")
        return
    for to_upload in os.listdir(wdir_path + '/waves/txt'):
        if to_upload.split('.')[-1] != 'csv': # TODO replace csv by ta when available
            continue
        logging.info('uploading {}'.format(to_upload))
        r = observateur.post('{}/fichiers'.format(settings.BACKEND_DOMAIN),
            json={'titre': to_upload, 'mime': 'application/ta'},
            auth=(settings.SECRET_KEY, None))
        if r.status_code != 200:
            raise S3Error('Cannot init file creation {} : {}, {}'.format(
                to_upload, r.status_code, r.text))
        file_info = r.json()
        r = requests.post(file_info['s3_signed_url'],
            files={'file': open('{}/{}'.format(wdir_path, to_upload), 'rb')})
        if r.status_code != 200:
            raise S3Error('Cannot upload to S3 file {} : {}, {}'.format(
                to_upload, r.status_code, r.text))
        r = observateur.post('/fichiers/' + file_info['_id'],
                             auth=(settings.SECRET_KEY, None))
        if r.status_code != 200:
            raise S3Error('Cannot finalize file {} : {}, {}'.format(
                to_upload, r.status_code, r.text))


def _create_working_dir():
    wdir  = tempfile.mkdtemp()
    logging.info('working in directory {}'.format(wdir))
    os.mkdir(wdir + '/waves')
    return wdir


@celery_app.task
def run_tadarida_d():
    db = MongoClient(host=settings.get_mongo_uri())[settings.MONGO_DBNAME]
    while True:
        wdir_path = _create_working_dir()
        # Get back the list of fichiers requesting a ride with tadaridaD
        cursor = db.fichiers.find({'require_process': 'tadaridaD'}, limit=50)
        count = cursor.count()
        total = cursor.count(with_limit_and_skip=False)
        logging.info('found {} files requiring tadaridaD'.format(total))
        if not total:
            # Nothing to do, just leave
            return
        _download_files(wdir_path, cursor)
        # Run tadarida
        logging.info('running tadaridaD')
        ret = subprocess.call([TADARIDA_D, 'waves'], cwd=wdir_path)
        if ret:
            logging.error('Error in running tadaridaD : returns {}'.format(ret))
        _upload_results(wdir_path)
        # Continue until no more fichier request to be processed
        if count == total:
            break


@celery_app.task
def run_tadarida_c():
    logging.error('run_tadarida_c is not implemented yet')
