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
from ..xin.snippets import Paginator, get_url_params
from ..xin.tools import parse_id


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


def _create_actuality(lookup, document):
    try:
        result = actualites.insert_or_replace(lookup, document, auto_abort=False)
        return result
    except DocumentException as e:
        logging.error('error inserting actuality {} : {}'.format(
            document, e))
        return None


def create_actuality_nouveau_site(site_id, observateur_id, protocole_id):
    document = {'action': 'NOUVEAU_SITE',
                'site': site_id,
                'sujet': observateur_id,
                'protocole': protocole_id,
                'resources': [site_id, observateur_id, protocole_id]}
    lookup = {'action': 'NOUVEAU_SITE',
              'site': site_id}
    return _create_actuality(lookup, document)


def create_actuality_verrouille_site(site_id, utilisateur_id):
    # Update previously created NOUVEAU_SITE actuality to
    # notify the lock date
    lookup = {'action': 'NOUVEAU_SITE',
              'site': site_id}
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
    site_id = participation['site']
    document = {'action': 'NOUVELLE_PARTICIPATION',
                'participation': participation_id,
                'sujet': sujet_id,
                'site': site_id,
                'resources': [participation_id, sujet_id, site_id]}
    lookup = {'action': 'NOUVELLE_PARTICIPATION',
              'participation': participation_id}
    return _create_actuality(lookup, document)


def create_actuality_inscription_protocole_batch(sujet_id, protocoles, inscription_validee=False):
    now = datetime.utcnow()
    for protocole_id in protocoles:
        document = {
            'action': 'INSCRIPTION_PROTOCOLE',
            'protocole': protocole_id,
            'sujet': sujet_id,
            'resources': [protocole_id, sujet_id]
        }
        lookup = {
            'action': 'INSCRIPTION_PROTOCOLE',
            'protocole': protocole_id,
            'sujet': sujet_id,
        }
        if inscription_validee:
            document['date_validation'] = now
        _create_actuality(lookup, document)


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
    lookup = {'resources': {'$in': following}}
    found = actualites.find(lookup, sort=[('_updated', -1)],
                            skip=pagination.skip,
                            limit=pagination.max_results)
    return pagination.make_response(*found)


@actualites.route('/actualites/validations', methods=['GET'])
@requires_auth(roles='Observateur')
def get_actualites_validations():
    pagination = Paginator()
    lookup = {'action': 'INSCRIPTION_PROTOCOLE'}
    params = get_url_params({'protocole': False, 'type': False})
    if 'protocole' in params:
        lookup['protocole'] = parse_id(params['protocole'])
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
                            skip=pagination.skip,
                            limit=pagination.max_results)
    return pagination.make_response(*found)
