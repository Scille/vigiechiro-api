"""
Tadarida-C task worker
"""

import logging
import sys
import os
import tempfile
import subprocess
import requests
import csv

from .celery import celery_app
from .. import settings
from ..resources.fichiers import ALLOWED_MIMES_TA


MIN_PROBA_TAXON = 0.05
TADARIDA_C = os.path.abspath(os.path.dirname(__file__)) + '/../../bin/tadaridaC'
BACKEND_DOMAIN = settings.BACKEND_DOMAIN
AUTH = (settings.SCRIPT_WORKER_TOKEN, None)


def _create_working_dir(subdirs):
    wdir  = tempfile.mkdtemp()
    logging.info('working in directory {}'.format(wdir))
    for subdir in subdirs:
        os.mkdir(wdir + '/' + subdir)
    return wdir


def _make_taxon_observation(taxon_name, taxon_proba):
    r = requests.get('{}/taxons'.format(BACKEND_DOMAIN),
        params={'q': taxon_name}, auth=AUTH)
    if r.status_code != 200:
        logging.warning('retreiving taxon {} in backend, error {}: {}'.format(
            taxon_name, r.status_code, r.text))
        return None
    if r.json()['_meta']['total'] == 0:
        logging.warning('cannot retreive taxon {} in backend, skipping it'.format(
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
        logging.error('Cannot retreive fichier {}'.format(fichier_id))
        return 1
    fichier = r.json()
    fichier_info = '{} ({})'.format(fichier['_id'], fichier['titre'])
    if fichier['mime'] not in ALLOWED_MIMES_TA:
        logging.error('Fichier {} is not a ta file (mime: {})'.format(
            fichier_info, fichier['mime']))
        return 1
    if 'lien_donnee' not in fichier:
        logging.error('{} must have a lien_donnee in order to link '
                      'the generated .tc to something'.format(fichier_info))
        return 1
    # Download the file
    logging.info('Downloading file {}'.format(fichier_info))
    r = requests.get('{}/fichiers/{}/acces'.format(BACKEND_DOMAIN, fichier_id),
        params={'redirection': True}, stream=True, auth=AUTH)
    input_path = wdir_path + '/tas/' + fichier['titre']
    with open(input_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024): 
            if chunk: # filter out keep-alive new chunks
                f.write(chunk)
                f.flush()
    if r.status_code != 200:
        logging.error('Cannot get back file {} : {}, {}'.format(
            fichier_info, r.status_code, r.text))
        return 1
    logging.info('Got back file {}, running tadaridaC on it'.format(fichier_info))
    # Run tadarida
    ret = subprocess.call([TADARIDA_C, 'tas'], cwd=wdir_path)
    if ret:
        logging.error('Error in running tadaridaC : returns {}'.format(ret))
        return 1
    # A output.tc file should have been generated
    output_path = wdir_path + '/tas/output.tc'
    # output.tc is too generic, rename it according to original .ta file
    output_name = fichier['titre'].rsplit('.', 1)[0] + '.tc'
    if not os.path.exists(output_path):
        logging.warning("{} hasn't been created, hence {} has"
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
        logging.error("{}'s .tc backend post {} error {} : {}".format(
            fichier_info, tc_payload, r.status_code, r.text))
        return 1
    tc_data = r.json()
    tc_fichier_info = '{} ({})'.format(tc_data['_id'], tc_data['titre'])
    logging.info("Registered {}'s .ta as {}".format(fichier_info, tc_fichier_info))
    # Then put it to s3 with the signed url
    s3_signed_url = tc_data['s3_signed_url']
    with open(output_path, 'rb') as fd:
        r = requests.put(s3_signed_url, headers={'Content-Type': tc_payload['mime']}, data=fd)
    if r.status_code != 200:
        logging.error('post to s3 {} error {} : {}'.format(s3_signed_url, r.status_code, r.text))
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
        logging.warning('updating donnee {}, error {}: {}'.format(
            fichier['lien_donnee'], r.status_code, r.text))
        return 1
    # Notify the upload to the backend
    r = requests.post(BACKEND_DOMAIN + '/fichiers/' + tc_data['_id'], auth=AUTH)
    if r.status_code != 200:
        logging.error('Notify end upload for {} error {} : {}'.format(
            tc_data['_id'], r.status_code, r.text))
        return 1
    return 0
