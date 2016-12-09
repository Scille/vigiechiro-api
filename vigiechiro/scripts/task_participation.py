

#! /usr/bin/env python3

"""
Participation bilan task worker
"""

import logging
logging.basicConfig()
base_logger = logging.getLogger('task')
base_logger.setLevel(logging.INFO)
from datetime import datetime
from uuid import uuid4
import csv
import shutil
import tempfile
import subprocess
import requests
import os
import re
from bson import ObjectId
from flask import current_app, g
from concurrent.futures import ThreadPoolExecutor
from traceback import format_exc
from flask.ext.mail import Message

from ..settings import (BACKEND_DOMAIN, SCRIPT_WORKER_TOKEN, TADARIDA_D_OPTS,
                        TADARIDA_C_OPTS, TADARIDA_C_BATCH_SIZE, TASK_PARTICIPATION_BATCH_SIZE,
                        TASK_PARTICIPATION_DATASTORE_CACHE, REQUESTS_TIMEOUT)
from ..resources.fichiers import (fichiers as fichiers_resource, ALLOWED_MIMES_PHOTOS,
                                  ALLOWED_MIMES_TA, ALLOWED_MIMES_TC, ALLOWED_MIMES_WAV,
                                  delete_fichier_and_s3, get_file_from_s3)
from .queuer import task


DOWNLOAD_POOL_SIZE = 10


class ProxyLogger:
    LOGS = []
    def log(self, level, msg, *args, skip_print=False, store=True, **kwargs):
        logger_level = getattr(logging, level.upper())
        if not skip_print:
            base_logger.log(logger_level, msg, *args, **kwargs)
        if store:
            self.LOGS.append({'level': level, 'message': msg, 'date': datetime.utcnow()})
    def info(self, *args, **kwargs):
        self.log('info', *args, **kwargs)
    def warning(self, *args, **kwargs):
        self.log('warning', *args, **kwargs)
    def error(self, *args, **kwargs):
        self.log('error', *args, **kwargs)
    def debug(self, *args, **kwargs):
        self.log('debug', *args, store=False, **kwargs)
logger = ProxyLogger()


MIN_PROBA_TAXON = 0.20
TADARIDA_C = os.path.abspath(os.path.dirname(__file__)) + '/../../bin/tadaridaC'
TADARIDA_D = os.path.abspath(os.path.dirname(__file__)) + '/../../bin/tadaridaD'
ORDER_NAMES = [('Chiroptera', 'chiropteres'), ('Orthoptera', 'orthopteres')]
AUTH = (SCRIPT_WORKER_TOKEN, None)


def _create_working_dir(subdirs=()):
    wdir = tempfile.mkdtemp()
    for subdir in subdirs:
        os.mkdir(wdir + '/' + subdir)
    return wdir


def _create_fichier(titre, mime, proprietaire, data_path=None, data_raw=None, **kwargs):
    if mime == 'audio/wav':
        s3_dir = 'wav/'
    elif mime == 'application/ta':
        s3_dir = 'ta/'
    elif mime == 'application/tc':
        s3_dir = 'tc/'
    else:
        s3_dir = 'others/'
    from ..resources.fichiers import fichiers as f_resource, _sign_request
    payload = {'titre': titre,
               'proprietaire': proprietaire,
               'mime': mime,
               's3_id': s3_dir + titre + '.' + uuid4().hex,
               'disponible': True}
    payload.update(kwargs)
    # Upload the fichier to S3
    sign = _sign_request(verb='PUT', object_name=payload['s3_id'],
                         content_type=payload['mime'])
    if data_path:
        with open(data_path, 'rb') as fd:
            r = requests.put(sign['signed_url'],
                             headers={'Content-Type': mime}, data=fd,
                             timeout=REQUESTS_TIMEOUT)
    elif data_raw:
        r = requests.put(sign['signed_url'],
                         headers={'Content-Type': mime},
                         data=data_raw,
                         timeout=REQUESTS_TIMEOUT)
                         # files={'file': ('', data_raw)})
    if r.status_code != 200:
        logger.error('Uploading to S3 {} error {} : {}'.format(
            payload, r.status_code, r.text))
        return 1
    # Then store it representation in database
    return f_resource.insert(payload)


NAME_TO_TAXON = {}
def _get_taxon(taxon_name):
    taxon = NAME_TO_TAXON.get(taxon_name)
    if not taxon:
        r = requests.get('{}/taxons'.format(BACKEND_DOMAIN),
            params={'q': taxon_name}, auth=AUTH,
            timeout=REQUESTS_TIMEOUT)
        if r.status_code != 200:
            logger.warning('retreiving taxon {} in backend, error {}: {}'.format(
                taxon_name, r.status_code, r.text))
            return None
        if r.json()['_meta']['total'] == 0:
            logger.warning('cannot retreive taxon {} in backend, skipping it'.format(
                taxon_name))
            return None
        taxon = r.json()['_items'][0]
        NAME_TO_TAXON[taxon_name] = taxon
    return taxon


def _list_donnees(participation_id):
    processed = 0
    page = 1
    max_results = 100
    while True:
        r = requests.get(BACKEND_DOMAIN + '/participations/{}/donnees'.format(participation_id),
            auth=AUTH, params={'page': page, 'max_results': max_results},
            timeout=REQUESTS_TIMEOUT)
        if r.status_code != 200:
            logger.warning("retreiving participation {}'s donnees, error {}: {}".format(
                participation_id, r.status_code, r.text))
            return None
        result = r.json()
        items = result['_items']
        processed += result['_meta']['max_results']
        for item in items:
            yield item
        page += 1
        if processed >= result['_meta']['total']:
            break


class Bilan:

    # Keep it global to save ressources if the worker as more than one task
    taxon_to_order_name = {}

    def __init__(self):
        self.bilan_order = {}
        self.taxon_to_order_name = {}
        self.problemes = 0

    def _define_taxon_order(self, taxon):
        logger.debug("Lookuping for taxon order for {}".format(
            taxon['_id'], taxon['libelle_court']))
        taxon_id = taxon['_id']
        if taxon_id in self.taxon_to_order_name:
            order_name = self.taxon_to_order_name[taxon_id]
        else:
            def recursive_order_find(taxon):
                logger.debug("Recursive lookup on taxon {} ({})".format(
                    taxon['_id'], taxon['libelle_court']))
                for order_name_compare, order_name in ORDER_NAMES:
                    if (taxon['libelle_long'] == order_name_compare
                        or taxon['libelle_court'] == order_name_compare):
                        return order_name
                for parent_id_or_data in taxon.get('parents', []):
                    if isinstance(parent_id_or_data, dict):
                        parent_id = parent_id_or_data['_id']
                    else:
                        parent_id = parent_id_or_data
                    r = requests.get(
                        BACKEND_DOMAIN + '/taxons/{}'.format(parent_id),
                        auth=AUTH, timeout=REQUESTS_TIMEOUT)
                    if r.status_code != 200:
                        logger.error('Retrieving taxon {} error {} : {}'.format(
                            parent_id, r.status_code, r.text))
                        return 1
                    parent = r.json()
                    order = recursive_order_find(parent)
                    if order != 'autre':
                        return order
                return 'autre'
            order_name = recursive_order_find(taxon)
            if order_name not in self.bilan_order:
                self.bilan_order[order_name] = {}
            self.taxon_to_order_name[taxon_id] = order_name
        order = self.bilan_order[order_name]
        if taxon_id not in order:
            order[taxon_id] = {'contact_max': 0, 'contact_min': 0}
        return self.bilan_order[order_name]

    def add_contact_min(self, taxon, proba):
        if proba > 0.75:
            order = self._define_taxon_order(taxon)
            order[taxon['_id']]['contact_min'] += 1

    def add_contact_max(self, taxon, proba):
        order = self._define_taxon_order(taxon)
        order[taxon['_id']]['contact_max'] += 1

    def generate_payload(self):
        payload = {'problemes': self.problemes}
        for order_name, order in self.bilan_order.items():
            payload[order_name] = [{'taxon': taxon, 'nb_contact_min': d['contact_min'], 'nb_contact_max': d['contact_max']}
                                   for taxon, d in order.items()]
        return payload


@task
def participation_generate_bilan(participation_id):
    participation_id = str(participation_id)
    bilan = Bilan()
    # Retreive all the participation's donnees and draw some stats about them
    for donnee in _list_donnees(participation_id):
        if 'probleme' in donnee:
            bilan.problemes += 1
        for observation in donnee.get('observations', []):
            bilan.add_contact_max(observation['tadarida_taxon'], observation['tadarida_probabilite'])
            bilan.add_contact_min(observation['tadarida_taxon'], observation['tadarida_probabilite'])
    # Update the participation
    logger.info('participation {}, bilan : {}'.format(participation_id, bilan.generate_payload()))
    r = requests.patch(BACKEND_DOMAIN + '/participations/' + participation_id,
                       json={'bilan': bilan.generate_payload()}, auth=AUTH,
                       timeout=REQUESTS_TIMEOUT)
    if r.status_code != 200:
        logger.error('Cannot update bilan for participation {}, error {} : {}'.format(
            participation_id, r.status_code, r.text))
        return 1
    return 0


@task
def process_participation(participation_id, pjs_ids=[], publique=True,
                          notify_mail=None, notify_msg=None):
    participation_id = ObjectId(participation_id)
    pjs_ids = [ObjectId(x) for x in pjs_ids]
    from ..app import app as flask_app
    from ..resources.participations import participations as p_resource
    p = p_resource.find_one(participation_id, fields={
        'protocole': False, 'messages': False, 'logs': False, 'bilan': False})
    traitement = {'etat': 'EN_COURS', 'date_debut': datetime.utcnow()}
    p_resource.update(participation_id, {'traitement': traitement}, auto_abort=False)
    try:
        _process_participation(participation_id, pjs_ids=pjs_ids, publique=publique)
    except:
        msg = format_exc()
        logger.error(msg)
        traitement['etat'] = 'ERREUR'
        traitement['date_fin'] = datetime.utcnow()
        traitement['message'] = msg
        p_resource.update(participation_id, {'traitement': traitement}, auto_abort=False)
    else:
        traitement['etat'] = 'FINI'
        traitement['date_fin'] = datetime.utcnow()
        p_resource.update(participation_id, {'traitement': traitement}, auto_abort=False)
    if not notify_mail:
        return
    if isinstance(notify_mail, str):
        notify_mail = [notify_mail]
    site_name = p['site']['titre']
    msg = Message(
        subject="Votre participation vient d'être traitée !",
        recipients=notify_mail, body=notify_msg)
    current_app.mail.send(msg)


def _process_participation(participation_id, pjs_ids=[], publique=True):
    participation_id = str(participation_id)
    wdir = _create_working_dir(('D', 'C'))
    logger.info("Starting building participation %s" % participation_id)
    g.request_user = {'role': 'Administrateur'}
    try:
        participation = Participation(participation_id, pjs_ids, publique)
    except ParticipationError as e:
        logger.error(e)
        return
    participation.reset_pjs_state()
    participation.load_pjs()
    run_tadaridaD(wdir + '/D', participation)
    run_tadaridaC(wdir + '/C', participation)
    participation.save()
    shutil.rmtree(wdir)
    participation_generate_bilan(participation_id)


class Fichier:
    def __init__(self, fichier=None, **kwargs):
        if fichier:
            self.id = fichier['_id']
            self.titre = fichier['titre']
            self.mime = fichier['mime']
        else:
            self.id = kwargs.get('id')
            self.titre = kwargs.get('titre')
            self.mime = kwargs.get('mime', self.DEFAULT_MIME)
            self.data_path = kwargs.get('path')
        self.doc = fichier

    @property
    def cir_canal(self):
        # Display canal only for protocoles "routier" and "pedestre"
        if not self.titre.startswith("Cir"):
            return None
        try:
            return 'DROITE' if re.search(
                r'^Cir.+-[0-9]{4}-Pass[0-9]{1,2}-Tron[0-9]{1,2}-Chiro_([01]_)?[0-9]+_[0-9]{3}',
                self.titre).group(1) == '1_' else 'GAUCHE'
        except AttributeError:
            return None


    @property
    def basename(self):
        if self.titre:
            return self.titre.rsplit('.', 1)[0]

    def _get_from_datastore(self, target_path):
        assert TASK_PARTICIPATION_DATASTORE_CACHE
        datastore_target = '%s/%s' % (TASK_PARTICIPATION_DATASTORE_CACHE, self.titre)
        if not os.path.exists(TASK_PARTICIPATION_DATASTORE_CACHE):
            return False
        else:
            os.symlink(datastore_target, target_path)
            return True

    def _populate_datastore_from_s3(self):
        assert TASK_PARTICIPATION_DATASTORE_CACHE
        if self.doc:
            self._get_from_s3(TASK_PARTICIPATION_DATASTORE_CACHE)
            return True
        else:
            return False

    def _populate_datastore_from_disk(self):
        assert TASK_PARTICIPATION_DATASTORE_CACHE
        datastore_target = '%s/%s' % (TASK_PARTICIPATION_DATASTORE_CACHE, self.titre)
        if self.data_path:
            shutil.copy(self.data_path, datastore_target)
            return True
        else:
            return False

    def _get_from_s3(self, target_path):
        r = get_file_from_s3(self.doc, target_path)
        if r.status_code != 200:
            logger.error('Cannot get back file {} ({}) : error {}'.format(
                self.id, self.doc['titre'], r.status_code))

    def _fetch_data_with_datastore(self, target_path):
        assert TASK_PARTICIPATION_DATASTORE_CACHE
        ret = self._get_from_datastore(target_path)
        if not ret:
            # Cache miss, try to populate through disk then S3
            if self._populate_datastore_from_disk():
                self._get_from_datastore(target_path)
            elif self._populate_datastore_from_s3():
                self._get_from_datastore(target_path)
            else:
                raise RuntimeError('Cannot fetch data for %s' % target_path)

    def _fetch_data(self, target_path):
        if self.doc:
            r = get_file_from_s3(self.doc, target_path)
            if r.status_code != 200:
                logger.error('Cannot get back file {} ({}) : error {}'.format(
                    self.id, self.doc['titre'], r.status_code))
        elif self.data_path:
            os.link(self.data_path, target_path)
        else:
            raise RuntimeError('Cannot fetch data for %s' % target_path)
        return target_path

    def fetch_data(self, path=''):
        if not self.doc and not self.data_path:
            raise ValueError('No data to fetch')
        target_path = '/'.join((path, self.titre))
        if TASK_PARTICIPATION_DATASTORE_CACHE:
            self._fetch_data_with_datastore(path)
        else:
            self._fetch_data(path)
        return target_path

    def save(self, donnee_id, participation_id, proprietaire_id):
        if self.id:
            # Fichier already in database, nothing to do...
            return
        inserted = _create_fichier(self.titre, self.mime, proprietaire_id,
                                   data_path=self.data_path,
                                   lien_donnee=donnee_id,
                                   lien_participation=participation_id,)
        self.id = inserted['_id']
        logger.debug('Fichier created: {} ({})'.format(self.id, self.titre))


class FichierWav(Fichier):
    DEFAULT_MIME = 'audio/wav'


class FichierTA(Fichier):
    DEFAULT_MIME = 'application/ta'


class FichierTC(Fichier):
    DEFAULT_MIME = 'application/tc'


class Donnee:
    def __init__(self, basename):
        self.basename = basename
        self.observations = []
        self.id = None
        self.wav = None
        self.tc = None
        self.ta = None

    def insert(self, fichier):
        fichier.donnee = self
        if isinstance(fichier, FichierWav):
            self.wav = fichier
        elif isinstance(fichier, FichierTA):
            self.ta = fichier
        elif isinstance(fichier, FichierTC):
            self.tc = fichier
            # TODO: update the donnee here

    def _build_observations(self):
        if not self.tc or not self.tc.data_path:
            return
        with open(self.tc.data_path, 'r') as fd:
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
                    elif float(cell) >= MIN_PROBA_TAXON:
                        # Interesting taxon
                        taxon_data = _get_taxon(head)
                        if not taxon_data:
                            logger.warning("Taxon `%s` doesn't exists" % head)
                            continue
                        taxon = {'taxon': taxon_data['_id'],
                                 'probabilite': float(cell)}
                        if taxon:
                            taxons.append(taxon)
                # Sort taxons by proba and retrieve taxon' resources in backend
                taxons = sorted(taxons, key=lambda x: x['probabilite'])
                if len(taxons):
                    main_taxon = taxons.pop()
                    obs['tadarida_taxon'] = main_taxon['taxon']
                    obs['tadarida_probabilite'] = main_taxon['probabilite']
                    obs['tadarida_taxon_autre'] = list(reversed(taxons))
                    self.observations.append(obs)


    def save(self, participation_id, proprietaire_id, publique):
        if self.id:
            return
        from ..resources.donnees import donnees as d_resource
        self._build_observations()
        payload = {
            'titre': self.basename,
            'participation': participation_id,
            'proprietaire': proprietaire_id,
            'publique': publique,
            'observations': self.observations
        }
        inserted = d_resource.insert(payload)
        self.id = inserted['_id']
        logger.debug('Creating donnee {} ({})'.format(self.id, self.basename))
        from ..app import app as flask_app
        def save_fichier(fichier, **kwargs):
            with flask_app.app_context():
                g.request_user = {'role': 'Administrateur'}
                fichier.save(**kwargs)
        with ThreadPoolExecutor(max_workers=DOWNLOAD_POOL_SIZE) as e:
            for fichier in (self.wav, self.tc, self.ta):
                if not fichier:
                    continue
                e.submit(save_fichier, fichier, donnee_id=self.id,
                         participation_id=participation_id,
                         proprietaire_id=proprietaire_id)


class ParticipationError(Exception): pass


class Participation:

    def __init__(self, participation_id, pjs_ids, publique):
        from ..resources.participations import participations as p_resource
        self.participation_id = participation_id
        self.participation = p_resource.get_resource(participation_id, auto_abort=False)
        if not self.participation:
            msg = 'Cannot retrieve participation %s' % participation_id
            raise ParticipationError(msg)
        self.publique = publique
        self.donnees = {}
        config = self.participation.get('configuration', {})
        # Values: GAUCHE, DROITE, ABSENT
        self.cir_expansion = config.get('canal_expansion_temps')
        self.cir_direct = config.get('canal_enregistrement_direct')
        # Register additional pjs as part of the participation
        current_app.data.db.fichiers.update({'_id': {'$in': pjs_ids}},
            {'$set': {'lien_participation': self.participation['_id']}}, multi=True)

    def reset_pjs_state(self):
        # Donnees will be recreated, delete them all
        ret = current_app.data.db.donnees.remove({
            'participation': self.participation['_id']
        })
        logger.info('Remove %s old donnees' % ret.get('n'))
        # Delete old .ta/.tc if needed to reset
        wav_pjs = current_app.data.db.fichiers.find({
            'lien_participation': self.participation['_id'],
            'mime': {'$in': ALLOWED_MIMES_WAV}
        })

        def clean_fichier(fichier):
            with flask_app.app_context():
                delete_fichier_and_s3(fichier)

        if wav_pjs.count():
            delete_pjs = current_app.data.db.fichiers.find({
                'lien_participation': self.participation['_id'],
                'mime': {'$in': ALLOWED_MIMES_TA + ALLOWED_MIMES_TC}
            })
            delete_pjs.batch_size(TASK_PARTICIPATION_BATCH_SIZE)
            logger.info("Participation base files are .wav, delete %s obsolete"
                        " .ta and .tc files" % delete_pjs.count())
            # TODO: parallelize this ?
            with ThreadPoolExecutor(max_workers=DOWNLOAD_POOL_SIZE) as e:
                for fichier in delete_pjs:
                    e.submit(clean_fichier, fichier)
            return
        ta_pjs = current_app.data.db.fichiers.find({
            'lien_participation': self.participation['_id'],
            'mime': {'$in': ALLOWED_MIMES_TA}
        })
        if ta_pjs.count():
            delete_pjs = current_app.data.db.fichiers.find({
                'lien_participation': self.participation['_id'],
                'mime': {'$in': ALLOWED_MIMES_TC}
            })
            delete_pjs.batch_size(TASK_PARTICIPATION_BATCH_SIZE)
            logger.info("Participation base files are .ta, delete %s obsolete"
                        " .tc files" % delete_pjs.count())
            with ThreadPoolExecutor(max_workers=DOWNLOAD_POOL_SIZE) as e:
                for fichier in delete_pjs:
                    e.submit(clean_fichier, fichier)
            return

    def load_pjs(self):
        pjs = [pj for pj in current_app.data.db.fichiers.find(
            {'lien_participation': self.participation['_id']})]
        pjs_ids_found = {pj['_id'] for pj in pjs}
        for pj in pjs:
            if pj['mime'] in ALLOWED_MIMES_WAV:
                obj = FichierWav(fichier=pj)
            elif pj['mime'] in ALLOWED_MIMES_TC:
                obj = FichierTC(fichier=pj)
            elif pj['mime'] in ALLOWED_MIMES_TA:
                obj = FichierTA(fichier=pj)
            else:
                continue # Other attachements are useless
            self._insert_file_obj(obj)

    def get_tas(self, cir_canal=None):
        for d in list(self.donnees.values()):
            if d.ta and (not cir_canal or cir_canal == d.ta.cir_canal):
                yield d.ta

    def get_tcs(self, cir_canal=None):
        for d in list(self.donnees.values()):
            if d.tc and (not cir_canal or cir_canal == d.tc.cir_canal):
                yield d.tc

    def get_waves(self, cir_canal=None):
        for d in list(self.donnees.values()):
            if d.wav and (not cir_canal or cir_canal == d.wav.cir_canal):
                yield d.wav

    def save(self):
        for d in self.donnees.values():
            d.save(self.participation['_id'],
                   self.participation['observateur'],
                   self.publique)
        from ..resources.participations import participations as p_resource
        logger.debug('Saving %s logs items in participation' % len(logger.LOGS))
        titre = 'participation-%s-logs' % (self.participation['_id'])
        new_logs = _create_fichier(titre, 'text/plain',
                                   self.participation['observateur'],
                                   data_raw=str(logger.LOGS),
                                   lien_participation=self.participation['_id'])
        old_logs = self.participation.get('logs')
        if old_logs:
            delete_fichier_and_s3(old_logs)
        p_resource.update(self.participation['_id'], {'logs': new_logs}, auto_abort=False)

    def _insert_file_obj(self, obj):
        if obj.basename not in self.donnees:
            self.donnees[obj.basename] = Donnee(obj.basename)
        self.donnees[obj.basename].insert(obj)

    def add_raw_file(self, path):
        titre = path.rsplit('/', 1)[-1]
        ext = titre.rsplit('.', 1)[-1]
        if ext == 'ta':
            obj = FichierTA(titre=titre, path=path)
        elif ext == 'tc':
            obj = FichierTC(titre=titre, path=path)
        elif ext == 'wav':
            obj = FichierWav(titre=titre, path=path)
        else:
            # Unknown file, just skip it
            return
        self._insert_file_obj(obj)


def run_tadaridaD(wdir_path, participation):
    # In case of cir participation, special work
    if participation.cir_direct and participation.cir_expansion:
        if participation.cir_expansion != 'ABSENT':
            wdir_path_cir = wdir_path + '/cir_expansion'
            os.mkdir(wdir_path_cir)
            _run_tadaridaD(wdir_path_cir, participation,
                           canal=participation.cir_expansion, expansion=10)
        if participation.cir_direct != 'ABSENT':
            wdir_path_cir = wdir_path + '/cir_direct'
            os.mkdir(wdir_path_cir)
            _run_tadaridaD(wdir_path_cir, participation,
                           canal=participation.cir_direct, expansion=1)
    else:
        _run_tadaridaD(wdir_path, participation)


def _run_tadaridaD(wdir_path, participation, expansion=10, canal=None):
    if expansion not in (10, 1):
        raise ValueError()
    logger.debug('Working in %s' % wdir_path)
    fichiers_count = 0
    from ..app import app as flask_app
    def fetch_data(fichier):
        with flask_app.app_context():
            fichier.fetch_data(wdir_path)
    with ThreadPoolExecutor(max_workers=DOWNLOAD_POOL_SIZE) as e:
        for fichier in participation.get_waves(canal):
            # e.submit(fichier.fetch_data, wdir_path)
            e.submit(fetch_data, fichier)
            fichiers_count += 1
    # Run tadarida
    logger.info('Starting tadaridaD with options `%s` and expansion x%s on %s files' %
                (TADARIDA_D_OPTS or '<no_options>', expansion, fichiers_count))
    ret = subprocess.call('2>&1 %s %s -x %s . | tee tadaridaD.log' %
                          (TADARIDA_D, TADARIDA_D_OPTS, str(expansion)),
                          cwd=wdir_path, shell=True)
    with open(wdir_path + '/tadaridaD.log', 'r') as fd:
        logger.info(' ---- TadaridaD output ----\n' + fd.read())
    # Now retreive the generated files
    # Save the error.log in the logs
    for root, _, files in os.walk(wdir_path + '/log'):
        for file_name in files:
            file_path = '/'.join((root, file_name))
            with open(file_path, 'r') as fd:
                data = fd.read()
            if data:
                logger.info(' ---- TadaridaD %s ----\n%s' % (file_path, data),
                            skip_print=True)
    if ret:
        msg = 'Error in running tadaridaD : returned {}'.format(ret)
        logger.error(msg)
        return 1
    if os.path.isdir(wdir_path + '/txt'):
        for file_name in os.listdir(wdir_path + '/txt/'):
            file_path = '%s/txt/%s' % (wdir_path, file_name)
            participation.add_raw_file(file_path)


def _run_tadaridaC(wdir_path, participation, fichiers_batch):
    if not fichiers_batch:
        return
    if not os.path.isdir(wdir_path):
        os.mkdir(wdir_path)
    from ..app import app as flask_app
    def fetch_data(fichier):
        with flask_app.app_context():
            fichier.fetch_data(wdir_path)
    with ThreadPoolExecutor(max_workers=DOWNLOAD_POOL_SIZE) as e:
        for fichier in fichiers_batch:
            e.submit(fetch_data, fichier)
    # Run tadarida
    logger.info('Starting tadaridaC with options `%s` on %s files %s (%s) to %s (%s)' %
                (TADARIDA_C_OPTS or '<no_options>', len(fichiers_batch),
                 fichiers_batch[0].id, fichiers_batch[0].titre,
                 fichiers_batch[-1].id, fichiers_batch[-1].titre))
    ret = subprocess.call(['2>&1 %s %s . | tee tadaridaC.log' % (TADARIDA_C, TADARIDA_C_OPTS)],
                          cwd=wdir_path, shell=True)
    with open(wdir_path + '/tadaridaC.log', 'r') as fd:
        logger.info(' ---- TadaridaC output ----\n' + fd.read())
    if ret:
        msg = 'Error in running tadaridaC : returned {}'.format(ret)
        logger.error(msg)
        return 1
    # Now retreive the generated files
    for file_name in os.listdir(wdir_path):
        if file_name.rsplit('.', 1)[-1] == 'tc':
            participation.add_raw_file('/'.join((wdir_path, file_name)))


def run_tadaridaC(wdir_path, participation):
    logger.debug('Working in %s' % wdir_path)
    batch = []
    batch_count = 1
    for i, fichier in enumerate(participation.get_tas(), 1):
        batch.append(fichier)
        if not (i % TADARIDA_C_BATCH_SIZE):
            _run_tadaridaC('%s/%s' % (wdir_path, batch_count), participation, batch)
            batch = []
            batch_count += 1
    if batch:
        _run_tadaridaC('%s/%s' % (wdir_path, batch_count), participation, batch)
    elif batch_count == 1:
        logger.info("No .ta files, tadaridaC doesn't need to be run")


if __name__ == '__main__':
    import sys
    from bson import ObjectId
    if len(sys.argv) != 2:
        raise SystemExit("usage: %s <participtaion_id>" %
                         os.path.basename(sys.argv[0]))
    process_participation(ObjectId(sys.argv[1]), [], True)
