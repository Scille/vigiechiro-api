#! /usr/bin/env python3

"""
Participation bilan task worker
"""

import logging
logger = logging.getLogger()
logger.setLevel(logging.WARNING)
import requests
from pymongo import MongoClient
from flask import current_app

from .celery import celery_app
from .. import settings
from ..settings import BACKEND_DOMAIN, SCRIPT_WORKER_TOKEN
from ..resources.fichiers import (fichiers as fichiers_resource, ALLOWED_MIMES_PHOTOS,
                                  ALLOWED_MIMES_TA, ALLOWED_MIMES_TC, ALLOWED_MIMES_WAV)


AUTH = (SCRIPT_WORKER_TOKEN, None)
ORDER_NAMES = [('Chiroptera', 'chiropteres'), ('Orthoptera', 'orthopteres')]


def _list_donnees(participation_id):
    processed = 0
    page = 1
    max_results = 100
    while True:
        r = requests.get(BACKEND_DOMAIN + '/participations/{}/donnees'.format(participation_id),
            auth=AUTH, params={'page': page, 'max_results': max_results})
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
        logger.info("Lookuping for taxon order for {}".format(
            taxon['_id'], taxon['libelle_court']))
        taxon_id = taxon['_id']
        if taxon_id in self.taxon_to_order_name:
            order_name = self.taxon_to_order_name[taxon_id]
        else:
            def recursive_order_find(taxon):
                logger.info("Recursive lookup on taxon {} ({})".format(
                    taxon['_id'], taxon['libelle_court']))
                for order_name_compare, order_name in ORDER_NAMES:
                    if (taxon['libelle_long'] == order_name_compare
                        or taxon['libelle_court'] == order_name_compare):
                        return order_name
                for parent_id in taxon.get('parents', []):
                    r = requests.get(BACKEND_DOMAIN + '/taxons/{}'.format(parent_id), auth=AUTH)
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



@celery_app.task
def participation_generate_bilan(participation_id):
    if not isinstance(participation_id, str):
        participation_id = str(participation_id)
    bilan = Bilan()
    # Retreive all the participation's donnees and draw some stats about them
    for donnee in _list_donnees(participation_id):
        if 'probleme' in donnee:
            bilan.problemes += 1
        for observation in donnee.get('observations', []):
            bilan.add_contact_max(observation['tadarida_taxon'], observation['tadarida_probabilite'])
            for obs in observation.get('tadarida_taxon_autre', []):
                bilan.add_contact_min(obs['taxon'], obs['probabilite'])
    # Update the participation
    logger.info('participation {}, bilan : {}'.format(participation_id, bilan.generate_payload()))
    r = requests.patch(BACKEND_DOMAIN + '/participations/' + participation_id,
                       json={'bilan': bilan.generate_payload()}, auth=AUTH)
    if r.status_code != 200:
        logger.error('Cannot update bilan for participation {}, error {} : {}'.format(
            participation_id, r.status_code, r.text))
        return 1
    return 0


def _participation_add_pj(participation, pjs, publique):
    from ..resources.donnees import donnees
    participation_id = participation['_id']
    to_link_donnees = {}
    async_process_tadaridaC = []
    async_process_tadaridaD = []
    no_process = []
    def add_to_link_donnees(pj_data):
        basename = pj_data['titre'].rsplit('.', 1)[0]
        if basename not in to_link_donnees:
            to_link_donnees[basename] = []
        to_link_donnees[basename].append(pj_data['_id'])
    for pj_data in pjs:
        pj_id = pj_data['_id']
        for link in 'lien_donnee', 'lien_participation', 'lien_protocole':
            if link in pj_data:
                logger.warning("Fichiers %s already linked to %s with"
                               " a `%s` field" % (pj_id, pj['link'], link))
                continue
        if pj_data['mime'] in ALLOWED_MIMES_WAV:
            add_to_link_donnees(pj_data)
            async_process_tadaridaD.append(pj_id)
        elif pj_data['mime'] in ALLOWED_MIMES_TA:
            add_to_link_donnees(pj_data)
            async_process_tadaridaC.append(pj_id)
            continue
        elif pj_data['mime'] in ALLOWED_MIMES_TC:
            add_to_link_donnees(pj_data)
            no_process.append(pj_id)
        elif pj_data['mime'] not in ALLOWED_MIMES_PHOTOS:
            logger.warning("Fichier %s has invalid mime %s" % (pj_id, pj['mime']))
    # If we are here, everything is ok, we can start altering the bdd
    simple_link = no_process + async_process_tadaridaD
    if simple_link:
        current_app.data.db.fichiers.update(
            {'_id': {'$in': simple_link}},
            {'$set': {'lien_participation': participation_id}},
            multi=True)
    # TadaridaC has a heavy bootstraping cost, hence we use batch
    # processing instead of per-file
    if async_process_tadaridaC:
        current_app.data.db.fichiers.update(
            {'_id': {'$in': async_process_tadaridaC}},
            {'$set': {'lien_participation': participation_id,
                      '_async_process': 'tadaridaC'}},
            multi=True)
    # Now retrieve or create the donnees
    donnees_db = current_app.data.db['donnees']
    fichiers_db = current_app.data.db['fichiers']
    donnees_per_titre = {}
    for basename, to_link in to_link_donnees.items():
        donnee = donnees_per_titre.get(basename, None)
        if not donnee:
            donnee = donnees_db.find_one({
                'titre': basename, 'participation': participation_id})
        if not donnee:
            payload = {
                'titre': basename,
                'participation': participation_id,
                'proprietaire': participation['observateur'],
                'publique': publique
            }
            donnee = donnees.insert(payload)
            logger.info('creating donnee {} ({})'.format(
                donnee['_id'], basename))
        donnees_per_titre[basename] = donnee
        donnee_id = donnee['_id']
        logger.info('Settings files {} to donnee {}'.format(to_link, donnee_id))
        fichiers_db.update({'_id': {'$in': to_link}},
                           {'$set': {'lien_donnee': donnee_id}}, multi=True)
    from .task_tadarida_d import tadaridaD
    logger.info('Trigger tadaridaD for %s ficiers'.format(len(async_process_tadaridaD)))
    for fichier_id in async_process_tadaridaD:
        tadaridaD.delay(fichier_id)
    return 0


@celery_app.task
def participation_add_pj(participation_id, pjs_ids, publique):
    from ..app import app as flask_app
    from ..resources.participations import participations
    with flask_app.app_context():
        participation = participations.get_resource(participation_id)
        pjs = [pj for pj in current_app.data.db.fichiers.find({'_id': {'$in': pjs_ids}})]
        pjs_ids_found = {pj['_id'] for pj in pjs}
        for pj_id in pjs_ids:
            if pj_id not in pjs_ids_found:
                logger.warning("Fichiers %s doesn't exsits" % pj_id)
        return _participation_add_pj(participation, pjs, publique)
