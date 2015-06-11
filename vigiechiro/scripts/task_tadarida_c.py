"""
Tadarida-C task worker
"""

import logging
logger = logging.getLogger()
logger.setLevel(logging.WARNING)
import sys
import os
import tempfile
import subprocess
import requests
import csv
from pymongo import MongoClient

from .celery import celery_app
from .. import settings
from ..resources.fichiers import fichiers, ALLOWED_MIMES_TA
from .task_participation import participation_generate_bilan


MIN_PROBA_TAXON = 0.05
TADARIDA_C = os.path.abspath(os.path.dirname(__file__)) + '/../../bin/tadaridaC'
BACKEND_DOMAIN = settings.BACKEND_DOMAIN
AUTH = (settings.SCRIPT_WORKER_TOKEN, None)


def _create_working_dir(subdirs):
    wdir  = tempfile.mkdtemp()
    logger.info('working in directory {}'.format(wdir))
    for subdir in subdirs:
        os.mkdir(wdir + '/' + subdir)
    return wdir


def _make_taxon_observation(taxon_name, taxon_proba):
    r = requests.get('{}/taxons'.format(BACKEND_DOMAIN),
        params={'q': taxon_name}, auth=AUTH)
    if r.status_code != 200:
        logger.warning('retreiving taxon {} in backend, error {}: {}'.format(
            taxon_name, r.status_code, r.text))
        return None
    if r.json()['_meta']['total'] == 0:
        logger.warning('cannot retreive taxon {} in backend, skipping it'.format(
            taxon_name))
        return None
    return {'taxon': r.json()['_items'][0]['_id'], 'probabilite': taxon_proba}


@celery_app.task
def tadaridaC(fichier_id):
    if not isinstance(fichier_id, str):
        fichier_id = str(fichier_id)
    wdir_path = _create_working_dir(['tas'])
    # Retreive the fichier resource
    r = requests.get(BACKEND_DOMAIN + '/fichiers/' + fichier_id, auth=AUTH)
    if r.status_code != 200:
        logger.error('Cannot retreive fichier {}'.format(fichier_id))
        return 1
    fichier = r.json()
    fichier_info = '{} ({})'.format(fichier['_id'], fichier['titre'])
    if fichier['mime'] not in ALLOWED_MIMES_TA:
        logger.error('Fichier {} is not a ta file (mime: {})'.format(
            fichier_info, fichier['mime']))
        return 1
    if 'lien_donnee' not in fichier:
        logger.error('{} must have a lien_donnee in order to link '
                      'the generated .tc to something'.format(fichier_info))
        return 1
    # Download the file
    logger.info('Downloading file {}'.format(fichier_info))
    r = requests.get('{}/fichiers/{}/acces'.format(BACKEND_DOMAIN, fichier_id),
        params={'redirection': True}, stream=True, auth=AUTH)
    input_path = wdir_path + '/tas/' + fichier['titre']
    with open(input_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024): 
            if chunk: # filter out keep-alive new chunks
                f.write(chunk)
                f.flush()
    if r.status_code != 200:
        logger.error('Cannot get back file {} : {}, {}'.format(
            fichier_info, r.status_code, r.text))
        return 1
    logger.info('Got back file {}, running tadaridaC on it'.format(fichier_info))
    # Run tadarida
    ret = subprocess.call([TADARIDA_C, 'tas'], cwd=wdir_path)
    if ret:
        logger.error('Error in running tadaridaC : returns {}'.format(ret))
        return 1
    # A output.tc file should have been generated
    output_path = wdir_path + '/tas/' + fichier['titre'].rsplit('.', 1)[0] + '.tc'
    output_name = output_path.split('/')[-1]
    if not os.path.exists(output_path):
        logger.warning("{} hasn't been created, hence {} has"
                        " not been processed".format(
                            output_name, fichier_info))
        return 1
    # Add the .tc as a fichier in the backend and upload it to S3
    tc_payload = {'titre': output_name,
                  'mime': 'application/tc',
                  'proprietaire': str(fichier['proprietaire']),
                  'lien_donnee': str(fichier['lien_donnee'])}
    if 'lien_participation' in fichier:
        tc_payload['lien_participation'] = str(fichier['lien_participation'])
    r = requests.post(BACKEND_DOMAIN + '/fichiers', json=tc_payload, auth=AUTH)
    if r.status_code != 201:
        logger.error("{}'s .tc backend post {} error {} : {}".format(
            fichier_info, tc_payload, r.status_code, r.text))
        return 1
    tc_data = r.json()
    tc_fichier_info = '{} ({})'.format(tc_data['_id'], tc_data['titre'])
    logger.info("Registered {}'s .ta as {}".format(fichier_info, tc_fichier_info))
    # Then put it to s3 with the signed url
    s3_signed_url = tc_data['s3_signed_url']
    with open(output_path, 'rb') as fd:
        r = requests.put(s3_signed_url, headers={'Content-Type': tc_payload['mime']}, data=fd)
    if r.status_code != 200:
        logger.error('post to s3 {} error {} : {}'.format(s3_signed_url, r.status_code, r.text))
        return 1
    # Update the donnee according to the .tc
    payload = {'observations': []}
    with open(output_path, 'r') as fd:
        reader = csv.reader(fd)
        headers = next(reader)
        for line in reader:
            taxons = []
            obs = {}
            for head, cell in zip(headers, line):
                if head in ['Group.1', 'Ordre', 'VersionD', 'VersionC']:
                    continue
                elif head == 'FreqM':
                    obs['frequence_mediane'] = float(cell)
                elif head == 'TDeb':
                    obs['temps_debut'] = float(cell)
                elif head == 'TFin':
                    obs['temps_fin'] = float(cell)
                elif float(cell) > MIN_PROBA_TAXON:
                    # Intersting taxon
                    taxon = _make_taxon_observation(head, float(cell))
                    if taxon:
                        taxons.append(taxon)
            # Sort taxons by proba and retrieve taxon' resources in backend
            taxons = sorted(taxons, key=lambda x: x['probabilite'])
            if len(taxons):
                main_taxon = taxons.pop()
                obs['tadarida_taxon'] = main_taxon['taxon']
                obs['tadarida_probabilite'] = main_taxon['probabilite']
                obs['tadarida_taxon_autre'] = list(reversed(taxons))
                payload['observations'].append(obs)
    r = requests.patch('{}/donnees/{}'.format(BACKEND_DOMAIN, fichier['lien_donnee']),
                       json=payload, auth=AUTH)
    if r.status_code != 200:
        logger.warning('updating donnee {}, error {}: {}'.format(
            fichier['lien_donnee'], r.status_code, r.text))
        return 1
    # Notify the upload to the backend
    r = requests.post(BACKEND_DOMAIN + '/fichiers/' + tc_data['_id'], auth=AUTH)
    if r.status_code != 200:
        logger.error('Notify end upload for {} error {} : {}'.format(
            tc_data['_id'], r.status_code, r.text))
        return 1
    return 0


def _tadaridaC_process_batch(db, batch):
    wdir_path = _create_working_dir(['tas'])
    # Sanity check
    fichiers_per_titre = {}
    for fichier in batch:
        # Add fichier_info among the real data for easier logging
        fichier['fichier_info'] = '{} ({})'.format(fichier['_id'], fichier['titre'])
        if fichier['mime'] not in ALLOWED_MIMES_TA:
            logger.error('Fichier {} is not a ta file (mime: {})'.format(
                fichier['fichier_info'], fichier['mime']))
        if 'lien_donnee' not in fichier:
            logger.error('{} must have a lien_donnee in order to link '
                          'the generated .tc to something'.format(
                              fichier['fichier_info']))
        fichiers_per_titre[fichier['titre']] = fichier
    # Download the files
    logger.info('Downloading {} files'.format(len(fichiers_per_titre)))
    for titre, fichier in fichiers_per_titre.items():
        r = requests.get('{}/fichiers/{}/acces'.format(
            BACKEND_DOMAIN, fichier['_id']), params={'redirection': True},
            stream=True, auth=AUTH)
        input_path = wdir_path + '/tas/' + titre
        with open(input_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)
                    f.flush()
        if r.status_code != 200:
            logger.error('Cannot get back file {} : error {}'.format(
                fichier['fichier_info'], r.status_code))
    logger.info('Got back files, running tadaridaC on them')
    # Run tadarida
    ret = subprocess.call([TADARIDA_C, 'tas'], cwd=wdir_path)
    fichiers_process_done = [f['_id'] for _, f in fichiers_per_titre.items()]
    if ret:
        logger.error('Error in running tadaridaC : returns {}'.format(ret))
        # TODO: tadaridaC provide error if file is empty leading to error loop
        logger.info('Mark as done fichiers {}'.format(fichiers_process_done))
        db.fichiers.update({'_id': {'$in': fichiers_process_done}},
                           {'$unset': {'_async_process': True}}, multi=True)
        return 1
    to_make_bilan = set()
    # Each .ta should have it .tc now
    for titre, fichier in fichiers_per_titre.items():
        output_name = titre.rsplit('.', 1)[0] + '.tc'
        output_path = wdir_path + '/tas/' + output_name
        if not os.path.exists(output_path):
            logger.warning("{} hasn't been created, hence {} has"
                            " not been processed".format(
                                output_name, fichier['fichier_info']))
            continue
        # Add the .tc as a fichier in the backend and upload it to S3
        tc_payload = {'titre': output_name,
                      'mime': 'application/tc',
                      'proprietaire': str(fichier['proprietaire']),
                      'lien_donnee': str(fichier['lien_donnee'])}
        if 'lien_participation' in fichier:
            tc_payload['lien_participation'] = str(fichier['lien_participation'])
        r = requests.post(BACKEND_DOMAIN + '/fichiers', json=tc_payload, auth=AUTH)
        if r.status_code != 201:
            logger.error("{}'s .tc backend post {} error {} : {}".format(
                fichier['fichier_info'], tc_payload, r.status_code, r.text))
            continue
        tc_data = r.json()
        tc_fichier_info = '{} ({})'.format(tc_data['_id'], tc_data['titre'])
        logger.info("Registered {}'s .ta as {}".format(
            fichier['fichier_info'], tc_fichier_info))
        # Then put it to s3 with the signed url
        s3_signed_url = tc_data['s3_signed_url']
        with open(output_path, 'rb') as fd:
            r = requests.put(s3_signed_url,
                headers={'Content-Type': tc_payload['mime']}, data=fd)
        if r.status_code != 200:
            logger.error('post to s3 {} error {} : {}'.format(
                s3_signed_url, r.status_code, r.text))
            continue
        # Notify the upload to the backend
        r = requests.post(BACKEND_DOMAIN + '/fichiers/' + tc_data['_id'], auth=AUTH)
        if r.status_code != 200:
            logger.error('Notify end upload for {} error {} : {}'.format(
                tc_data['_id'], r.status_code, r.text))
            continue
        # Update the donnee according to the .tc
        payload = {'observations': []}
        with open(output_path, 'r') as fd:
            reader = csv.reader(fd)
            headers = next(reader)
            for line in reader:
                taxons = []
                obs = {}
                for head, cell in zip(headers, line):
                    if head in ['Group.1', 'Ordre', 'VersionD', 'VersionC']:
                        continue
                    elif head == 'FreqM':
                        obs['frequence_mediane'] = float(cell)
                    elif head == 'TDeb':
                        obs['temps_debut'] = float(cell)
                    elif head == 'TFin':
                        obs['temps_fin'] = float(cell)
                    elif float(cell) > MIN_PROBA_TAXON:
                        # Intersting taxon
                        taxon = _make_taxon_observation(head, float(cell))
                        if taxon:
                            taxons.append(taxon)
                # Sort taxons by proba and retrieve taxon' resources in backend
                taxons = sorted(taxons, key=lambda x: x['probabilite'])
                if len(taxons):
                    main_taxon = taxons.pop()
                    obs['tadarida_taxon'] = main_taxon['taxon']
                    obs['tadarida_probabilite'] = main_taxon['probabilite']
                    obs['tadarida_taxon_autre'] = list(reversed(taxons))
                    payload['observations'].append(obs)
        # Force no bilan generation, given we will ask manually for them
        # not to trigger it multiple time
        r = requests.patch('{}/donnees/{}'.format(BACKEND_DOMAIN, fichier['lien_donnee']),
                           json=payload, auth=AUTH, params={'no_bilan': True})
        if r.status_code != 200:
            logger.warning('updating donnee {}, error {}: {}'.format(
                fichier['lien_donnee'], r.status_code, r.text))
            continue
        to_make_bilan.add(r.json()['participation']['_id'])
        # fichiers_process_done.append(fichier['_id'])
    # Remove the async process request from the original fichiers
    logger.info('Mark as done fichiers {}'.format(fichiers_process_done))
    db.fichiers.update({'_id': {'$in': fichiers_process_done}},
                       {'$unset': {'_async_process': True}}, multi=True)
    # Finally trigger the needed bilan generations
    logger.info('Schedule bilan regeneration for participations {}'.format(
        to_make_bilan))
    for participation_id in to_make_bilan:
        participation_generate_bilan.delay(participation_id)
    return 0

 
@celery_app.task
def tadaridaC_batch():
    db = MongoClient(host=settings.get_mongo_uri())[settings.MONGO_DBNAME]
    batch_size = 500
    while True:
        batch = db.fichiers.find({'_async_process': 'tadaridaC'}, limit=batch_size)
        if not batch.count():
            break
        _tadaridaC_process_batch(db, batch)


@celery_app.task
def tadaridaC_batch_watcher():
    db = MongoClient(host=settings.get_mongo_uri())[settings.MONGO_DBNAME]
    batch = db.fichiers.find({'_async_process': 'tadaridaC'}, limit=1)
    count = batch.count()
    if count:
        logger.info('Trigger tadaridaC batch for %s elements' % count)
        tadaridaC_batch.delay()
