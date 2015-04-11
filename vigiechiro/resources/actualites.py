"""
    Donnee actualité
    ~~~~~~~~~~~~~~~~

"""

import logging
from flask import g, request
from datetime import datetime

from ..xin import Resource, DocumentException
from ..xin.auth import requires_auth
from ..xin.schema import relation, choice
from ..xin.snippets import Paginator
from ..xin.tools import get_params


SCHEMA = {
    'resources': {
        'type': 'list',
        'schema': {'type': 'objectid'}
    },
    'action':  choice(['INSCRIPTION_PROTOCOLE',
                       'NOUVEAU_SITE',
                       'NOUVELLE_PARTICIPATION'], required=True),
    'sujet': relation('utilisateurs'),
    'site': relation('sites'),
    'protocole': relation('protocoles'),
    'participation': relation('participations'),
    'date_validation': {'type': 'datetime'},
    'date_refus': {'type': 'datetime'}
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


def create_actuality_verrouille_site(site, utilisateur):
    # Update previously created NOUVEAU_SITE actuality to
    # notify the lock date
    lookup = {'action': 'NOUVEAU_SITE',
              'sujet': utilisateur['_id'],
              'site': site['_id']}
    try:
        result = actualites.update(lookup,
                                   {'date_validation': datetime.utcnow()},
                                   auto_abort=False)
    except DocumentException as e:
        logging.error('error updating actuality with lookup {} : {}'.format(
            lookup, e))
        return None
    return result


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
    # Update previously created INSCRIPTION_PROTOCOLE actuality to
    # notify the validation date
    lookup = {'action': 'INSCRIPTION_PROTOCOLE',
              'sujet': utilisateur['_id'],
              'protocole': protocole['_id']}
    try:
        result = actualites.update(lookup,
                                   {'date_validation': datetime.utcnow()},
                                   auto_abort=False)
    except DocumentException as e:
        logging.error('error updating actuality with lookup {} : {}'.format(
            lookup, e))
        return None
    return result


def create_actuality_reject_protocole(protocole, utilisateur):
    # Update previously created INSCRIPTION_PROTOCOLE actuality to
    # notify the rejection date
    lookup = {'action': 'INSCRIPTION_PROTOCOLE',
              'sujet': utilisateur['_id'],
              'protocole': protocole['_id']}
    try:
        result = actualites.update(lookup,
                                   {'date_refus': datetime.utcnow()},
                                   auto_abort=False)
    except DocumentException as e:
        logging.error('error updating actuality with lookup {} : {}'.format(
            lookup, e))
        return None
    return result


@actualites.route('/moi/actualites', methods=['GET'])
@requires_auth(roles='Observateur')
def get_user_actualites():
    pagination = Paginator()
    following = g.request_user.get('actualites_suivies', [])
    following.append(g.request_user['_id'])
    expend = ['sujet', 'site', 'protocole', 'participation']
    lookup = {'resources': {'$in': following}}
    found = actualites.find(lookup, sort=[('_updated', -1)],
                            expend=expend, skip=pagination.skip,
                            limit=pagination.max_results)
    return pagination.make_response(*found)


@actualites.route('/actualites/validations', methods=['GET'])
@requires_auth(roles='Observateur')
def get_actualites_validations():
    pagination = Paginator()
    lookup = {'action': 'INSCRIPTION_PROTOCOLE'}
    params = get_params({'protocole': False, 'type': False})
    if 'protocole' in params:
        lookup['protocole'] = parse_id(lookup['protocole'])
        if not lookup['protocole']:
            abort(422, {'protocole': 'Bad ObjectId'})
    val_type = params.get('type', 'TOUS')
    if val_type == 'A_VALIDER':
        lookup['date_validation'] = {'$exists': False}
    elif val_type == 'VALIDES':
        lookup['date_validation'] = {'$exists': True}
    elif val_type != 'TOUS':
        abort(422, {'type': 'bad param type'})
    expend = ['sujet', 'protocole']
    found = actualites.find(lookup, sort=[('_updated', -1)],
                            expend=expend, skip=pagination.skip,
                            limit=pagination.max_results)
    return pagination.make_response(*found)
