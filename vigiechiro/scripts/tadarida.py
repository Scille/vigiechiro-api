import os
import logging
import tempfile
import requests
import bson
import subprocess
from pymongo import MongoClient

from .celery import celery_app
from .. import settings


AUTH = (settings.SCRIPT_WORKER_TOKEN, None)
TADARIDA_D = os.path.abspath(os.path.dirname(__file__)) + '/../../bin/tadaridaD'
TADARIDA_C = os.path.abspath(os.path.dirname(__file__)) + '/../../bin/tadaridaC'
logging.info('tadaridaD is {}'.format(TADARIDA_D))


class S3Error(Exception): pass


def _create_working_dir(subdirs):
    wdir  = tempfile.mkdtemp()
    logging.info('working in directory {}'.format(wdir))
    for subdir in subdirs:
        os.mkdir(wdir + '/' + subdir)
    return wdir


class ProcessItem:

    DB = None

    def __init__(self, doc, working_dir, expected_mime, expected_generate_name=None, expected_output_file=None):
        self._input_doc = doc
        self.expected_mime = expected_mime
        # Download the file
        self.file_info = '{} ({})'.format(doc['_id'], doc['titre'])
        logging.info('trying to get back file {}'.format(self.file_info))
        r = requests.get(
            '{}/fichiers/{}/acces'.format(settings.BACKEND_DOMAIN, doc['_id']),
            params={'redirection': True}, stream=True, auth=AUTH)
        self.input_file = working_dir + '/' + doc['titre']
        with open(self.input_file, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024): 
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)
                    f.flush()
        if r.status_code != 200:
            raise S3Error('Cannot get back file {} : {}, {}'.format(
                self.file_info, r.status_code, r.text))
        logging.info('got back file {}'.format(self.file_info))
        if not expected_output_file and not expected_generate_name:
            raise RuntimeError('expected_output_file or expected_generate_name must be present')
        if expected_output_file:
            self.expected_output_file = expected_output_file
        else:
            self.expected_output_file = expected_generate_name(self.input_file)

    def upload_result(self, require_process=None):
        if not os.path.exists(self.expected_output_file):
            logging.warning("{} hasn't been created, hence {} has"
                            " not been processed".format(
                                self.expected_output_file, self.file_info))
            return
        # Create a new fichier linked to the participation
        pj_data = {'titre': self.expected_output_file.split('/')[-1],
                   'mime': self.expected_mime,
                   'proprietaire': str(self._input_doc['proprietaire']),
                   'fichier_source': str(self._input_doc['_id'])}
        if require_process:
            pj_data['require_process'] = require_process
        if 'lien_participation' in self._input_doc:
            pj_data['lien_participation'] = str(self._input_doc['lien_participation'])
        r = requests.post(settings.BACKEND_DOMAIN + '/fichiers',
                          json=pj_data, auth=AUTH)
        if r.status_code != 201:
            logging.error('post {} error {} : {}'.format(pj_data, r.status_code, r.text))
            return
        pj_data = r.json()
        logging.info('Registered fichier {} ({})'.format(pj_data['_id'], pj_data['titre']))
        # Then post it to s3 with the signed url
        s3_signed_url = r.json()['s3_signed_url']
        r = requests.post(s3_signed_url,
                          files={'file': open(self.expected_output_file, 'rb')})
        if r.status_code != 200:
            logging.error('post to s3 {} error {} : {}'.format(s3_signed_url, r.status_code, r.text))
            return
        # Notify the upload to the backend
        r = requests.post(settings.BACKEND_DOMAIN + '/fichiers/' + pj_data['_id'],
                          auth=AUTH)
        if r.status_code != 200:
            logging.error('notify end upload for {} error {} : {}'.format(pj_data['_id'], r.status_code, r.text))
            return
        # Finally remove the process request in original fichier
        self.DB.fichiers.update({'_id': self._input_doc['_id']}, {'$unset': {'require_process': ""}})


@celery_app.task
def run_tadarida_d():
    db = MongoClient(host=settings.get_mongo_uri())[settings.MONGO_DBNAME]
    ProcessItem.DB = db
    while True: 
        wdir_path = _create_working_dir(['waves'])
        # Get back the list of fichiers requesting a ride with tadaridaD
        cursor = db.fichiers.find({'require_process': 'tadarida_d'}, limit=50)
        count = cursor.count()
        total = cursor.count(with_limit_and_skip=False)
        logging.info('found {} files requiring tadaridaD'.format(total))
        if not total:
            # Nothing to do, just leave
            return
        def expected_generate_name(input_file):
            path, name = input_file.rsplit('/', 1)
            return path + '/txt/' + name.rsplit('.', 1)[0] + '.ta'
        items = [ProcessItem(doc, wdir_path + '/waves', 'application/ta', expected_generate_name)
                 for doc in cursor]
        # Run tadarida
        logging.info('running tadaridaD')
        ret = subprocess.call([TADARIDA_D, 'waves'], cwd=wdir_path)
        if ret:
            logging.error('Error in running tadaridaD : returns {}'.format(ret))
        # Now upload back the results
        for item in items:
            item.upload_result(require_process='tadarida_c')
        # Continue until no more fichier request to be processed
        if count == total:
            break


@celery_app.task
def run_tadarida_c():
    db = MongoClient(host=settings.get_mongo_uri())[settings.MONGO_DBNAME]
    ProcessItem.DB = db
    while True:
        wdir_path = _create_working_dir(['tas'])
        # Get back the list of fichiers requesting a ride with tadaridaD
        cursor = db.fichiers.find({'require_process': 'tadarida_c'}, limit=50)
        count = cursor.count()
        total = cursor.count(with_limit_and_skip=False)
        logging.info('found {} files requiring tadaridaC'.format(total))
        if not total:
            # Nothing to do, just leave
            return
        def expected_generate_name(input_file):
            path, name = input_file.rsplit('/', 1)
            return path + '/' + name.rsplit('.', 1)[0] + '.tc'
        items = [ProcessItem(doc, wdir_path + '/tas', 'application/tc', expected_generate_name)
                 for doc in cursor]
        # Run tadarida
        logging.info('running tadaridaC')
        for item in items:
            ret = subprocess.call([TADARIDA_C, item.input_file], cwd=wdir_path)
            if ret:
                logging.error('Error in running tadaridaC : returns {}'.format(ret))
        # Now upload back the results
        for item in items:
            item.upload_result()
        # Continue until no more fichier request to be processed
        if count == total:
            break
