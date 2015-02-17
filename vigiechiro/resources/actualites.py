"""
    Donnee actualité
    ~~~~~~~~~~~~~~~~

"""

import logging
from flask import g

from ..xin import Resource, DocumentException
from ..xin.auth import requires_auth
from ..xin.schema import relation, choice
from ..xin.snippets import Paginator


SCHEMA = {
    'resources': {
        'type': 'list',
        'schema': {'type': 'objectid'}
    },
    'action':  choice(['INSCRIPTION_PROTOCOLE',
                       'VALIDATION_PROTOCOLE',
                       'NOUVEAU_SITE',
                       'NOUVELLE_PARTICIPATION'], required=True),
    'sujet': relation('utilisateurs'),
    'site': relation('sites'),
    'protocole': relation('protocoles'),
    'participation': relation('participations'),
}


actualites = Resource('actualites', __name__, schema=SCHEMA)


def _create_actuality(document):
    try:
        result = actualites.insert(document, auto_abort=False)
        return result
    except DocumentException as e:
        logging.error('error inserting actuality {} : {}'.format(
            document, e))
        return None


def create_actuality_nouveau_site(site):
    site_id = site['_id']
    sujet_id = site['observateur']
    document = {'action': 'NOUVEAU_SITE',
                'site': site_id,
                'sujet': sujet_id,
                'resources': [site_id, sujet_id]}
    return _create_actuality(document)


def create_actuality_nouvelle_participation(participation):
    participation_id = participation['_id']
    sujet_id = participation['observateur']
    document = {'action': 'NOUVELLE_PARTICIPATION',
                'participation': participation_id,
                'sujet': sujet_id,
                'resources': [participation_id, sujet_id]}
    return _create_actuality(document)


def create_actuality_inscription_protocole(protocole, utilisateur):
    protocole_id = protocole['_id']
    sujet_id = utilisateur['_id']
    document = {'action': 'INSCRIPTION_PROTOCOLE',
                'protocole': protocole_id,
                'sujet': sujet_id,
                'resources': [protocole_id, sujet_id]}
    return _create_actuality(document)


def create_actuality_validation_protocole(protocole, utilisateur):
    protocole_id = protocole['_id']
    sujet_id = utilisateur['_id']
    document = {'action': 'VALIDATION_PROTOCOLE',
                'protocole': protocole_id,
                'sujet': sujet_id,
                'resources': [protocole_id, sujet_id]}
    return _create_actuality(document)


@actualites.route('/moi/actualites', methods=['GET'])
@requires_auth(roles='Observateur')
def get_user_actualites():
    pagination = Paginator()
    following = g.request_user.get('actualites_suivies', [])
    following.append(g.request_user['_id'])
    found = actualites.find({'resources': {'$in': following}},
        skip=pagination.skip, limit=pagination.max_results)
    return pagination.make_response(*found)
