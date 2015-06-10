#! /usr/bin/env python3

"""
Participation bilan task worker
"""

import logging
logger = logging.getLogger()
logger.setLevel(logging.WARNING)
import requests

from .celery import celery_app
from ..settings import BACKEND_DOMAIN, SCRIPT_WORKER_TOKEN
from pymongo import MongoClient


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
