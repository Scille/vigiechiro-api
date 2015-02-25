import os
import logging
import tempfile
import requests
import bson
from pymongo import MongoClient

from .celery import celery_app
from .. import settings
from ..resources.fichiers import _sign_request


TADARIDA_D = os.path.abspath(os.path.dirname(__name__)) + '../../bin/tadaridaD'
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


def _upload_results(wdir_path, to_compute):
    for to_upload in os.listdir(wdir_path + '/waves/txt'):
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
    logging.info('Working in directory {}'.format(wdir.name))
    os.mkdir(wdir.name + '/waves')
    return wdir.name


def compute_files(to_compute):
    wdir_path = _create_working_dir()
    _download_files(wdir_path)
    # Run tadaridaD
    ret = subprocess.call([TADARIDA_D, 'waves'], cwd=wdir_path)
    if ret:
        logging.error('Error in running tadaridaD : returns {}'.format(ret))
    # Upload back results
    _upload_results(wdir_path)


@celery_app.task(bind=True)
def run_tadaridaD_on_participation(self, participation_id):
    try:
        participation_id = bson.ObjectId(participation_id)
    except bson.errors.InvalidId:
        logging.error('invalid ObjectId {}'.format(participation_id))
        return
    db = MongoClient(host=settings.get_mongo_uri())[settings.MONGO_DBNAME]
    participation = db.participations.find_one(participation_id)
    if not participation:
        logging.error('Cannot retrieve participation {}'.format(participation_id))
        return
    pjs = db.fichiers.find({'_id': {'$in': participation.get('pieces_jointes', [])}})
    waves = []
    tacs = []
    for pj in pjs:
        if pj['mime'] in ['sound/wav', 'audio/x-wav']:
            waves.append(pj)
        elif pj['mime'] in ['application/ta', 'application/tac']:
            tacs.append(pj)
    # Compute the wav with no equivalent ta/tac
    to_compute = []
    for pj in waves:
        title_no_extension, _ = pj['titre'].rsplit('.', 1)
        pj_computed = None
        for computed in tacs:
            if computed['titre'].rsplit('.', 1)[0] == title_no_extension:
                pj_computed = computed
                break
        if not pj_computed:
            # We need to compute the current pj
            to_compute.append(pj)
    try:
        compute_files(to_compute)
    except S3Error as e:
        logging.error(e)
        self.retry()


if __name__ == '__main__':
    import sys
    if len(sys.argv) == 2:
        run_tadaridaD_on_participation(sys.argv[1])
    else:
        raise SystemExit('Usage : {} <participation_id>'.format(sys.argv[0]))