#! /usr/bin/env python3

"""
Participation bilan task worker
"""

import logging
import requests

from .celery import celery_app
from ..settings import BACKEND_DOMAIN, SCRIPT_WORKER_TOKEN


AUTH = (SCRIPT_WORKER_TOKEN, None)


def _list_donnees(participation_id):
    processed = 0
    page = 0
    max_results = 100
    while True:
        r = requests.get(BACKEND_DOMAIN + '/participations/{}/donnees'.format(participation_id),
            auth=AUTH, params={'page': page, 'max_results': max_results})
        if r.status_code != 200:
            logging.warning("retreiving participation {}'s donnees, error {}: {}".format(
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
    def __init__(self):
        self.bilan_order = {}
        self.taxon_to_order_name = {}
        self.problemes = 0

    def _define_taxon_order(self, taxon):
        taxon_id = taxon['_id']
        if taxon_id in self.taxon_to_order_name:
            order_name = self.taxon_to_order_name[taxon_id]
        else:
            def recursive_order_find(taxon):
                for order_name in ['chiroptere', 'ortoptere']:
                    if (taxon['libelle_long'] == order_name
                        or taxon['libelle_court'] == order_name):
                        return order_name
                for parent_id in taxon.get('parents', []):
                    r = requests.get(BACKEND_DOMAIN + '/taxons/{}'.format(taxon_id), auth=AUTH)
                    if r.status_code != 200:
                        logging.error('Retrieving taxon {} error {} : {}'.format(
                            taxon_id, r.status_code, r.text))
                        return 1
                    parent = r.json()
                    get_taxon(parent_id)
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
        return self.bilan_order[order]

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
            payload[order_name] = [{'taxon': taxon, 'nb_contact_min': d[0], 'nb_contact_max': d[1]}
                                   for taxon, data in order.items()]
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
            for taxon, proba in observation.get('tadarida_taxon_autre', []).items():
                bilan.add_contact_min(taxon, proba)
    # Update the participation
    r = requests.patch(BACKEND_DOMAIN + '/participations/' + participation_id,
                       json={'bilan': bilan.generate_payload()}, auth=AUTH)
    if r.status_code != 200:
        logging.error('Cannot update bilan for participation {}'.format(participation_id))
        return 1
    return 0