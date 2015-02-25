"""
    Donnee participation
    ~~~~~~~~~~~~~~~~~~~~

    see: https://scille.atlassian.net/wiki/pages/viewpage.action?pageId=13893657
"""

from flask import abort, current_app, g
from datetime import datetime

from ..xin import Resource
from ..xin.tools import jsonify, abort, dict_projection
from ..xin.auth import requires_auth
from ..xin.schema import relation, choice
from ..xin.snippets import Paginator, get_payload, get_resource, get_lookup_from_q

from ..scripts.tadaridaD_on_participation import run_tadaridaD_on_participation

from .actualites import create_actuality_nouvelle_participation
from .fichiers import fichiers as fichiers_resource
from .utilisateurs import utilisateurs as utilisateurs_resource

SCHEMA = {
    'observateur': relation('utilisateurs', required=True),
    'protocole': relation('protocoles', required=True),
    'site': relation('sites', required=True),
    # 'numero': {'type': 'integer', 'required': True},
    'date_debut': {'type': 'datetime', 'required': True},
    'date_fin': {'type': 'datetime'},
    'meteo': {
        'type': 'dict',
        'schema': {
            'temperature_debut': {'type': 'integer'},
            'temperature_fin': {'type': 'integer'},
            'vent': choice(['NUL', 'FAIBLE', 'MOYEN', 'FORT']),
            'couverture': choice(['0-25', '25-50', '50-75', '75-100']),
        }
    },
    'commentaire': {'type': 'string'},
    'pieces_jointes': {
        'type': 'list',
        'schema': relation('fichiers', required=True)
    },
    'messages': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'auteur': relation('utilisateurs', required=True),
                'message': {'type': 'string', 'required': True},
                'date': {'type': 'datetime', 'required': True},
            }
        }
    },
    'configuration': {
        'type': 'dict',
        'schema': {
            'detecteur_enregistreur_numero_serie': {'type': 'string'},
            # TODO : create the custom_code type (dynamically
            # parametrized regex)
            # 'detecteur_enregistreur_type': {'type': 'custom_code'},
            'micro0_position': choice(['SOL', 'CANOPEE']),
            'micro0_numero_serie': {'type': 'string'},
            # 'micro0_type': {'type': 'custom_code'},
            'micro0_hauteur': {'type': 'integer'},
            'micro1_position': choice(['SOL', 'CANOPEE']),
            'micro1_numero_serie': {'type': 'string'},
            # 'micro1_type': {'type': 'custom_code'},
            'micro1_hauteur': {'type': 'integer'},
            # 'piste0_expansion': {'type': 'custom_code'},
            # 'piste1_expansion': {'type': 'custom_code'}
        }
    }
}

ALLOWED_MIMES = ['image/bmp', 'image/png', 'image/jpg',
                 'application/ta', 'application/tac',
                 'sound/wav', 'audio/x-wav']

participations = Resource('participations', __name__, schema=SCHEMA)


@participations.route('/participations', methods=['GET'])
@requires_auth(roles='Observateur')
def list_participations():
    pagination = Paginator()
    found = participations.find(get_lookup_from_q(), skip=pagination.skip,
                                limit=pagination.max_results)
    return pagination.make_response(*found)


@participations.route('/moi/participations', methods=['GET'])
@requires_auth(roles='Observateur')
def list_user_participations():
    pagination = Paginator()
    lookup = {'observateur': g.request_user['_id']}
    lookup.update(get_lookup_from_q() or {})
    found = participations.find(lookup,
                                 skip=pagination.skip,
                                 limit=pagination.max_results)
    return pagination.make_response(*found)


@participations.route('/participations/<objectid:participation_id>', methods=['GET'])
@requires_auth(roles='Observateur')
def display_participation(participation_id):
    document = participations.find_one(participation_id)
    # Remove pieces_jointes elements
    # TODO: optimize this
    if 'pieces_jointes' in document:
        del document['pieces_jointes']
    return document


@participations.route('/sites/<objectid:site_id>/participations', methods=['POST'])
@requires_auth(roles='Observateur')
def create_participation(site_id):
    # TODO : handle numero automatically
    # payload = get_payload({'numero': True, 'date_debut': False,
    payload = get_payload({'date_debut': False, 'date_fin': False,
                           'commentaire': False, 'meteo': False,
                           'configuration': False})
    payload['observateur'] = g.request_user['_id']
    payload['site'] = site_id
    site_resource = get_resource('sites', site_id, auto_abort=False)
    if not site_resource:
        abort(422, {'site': 'no site with this id'})
    if site_resource['observateur'] != g.request_user['_id']:
        abort(422, {'site': "observateur doesn't own this site"})
    if not site_resource.get('verrouille', False):
        abort(422, {'site': "cannot create protocole on an unlocked site"})
    protocole_id = site_resource['protocole']
    payload['protocole'] = protocole_id
    # Make sure observateur has joined protocole and is validated
    joined = next((p for p in g.request_user.get('protocoles', [])
                   if p['protocole'] == protocole_id), None)
    if not joined:
        abort(422, {'site': 'not registered to corresponding protocole'})
    document = participations.insert(payload)
    # Finally create corresponding actuality
    create_actuality_nouvelle_participation(document)
    if 'pieces_jointes' in document:
        del document['pieces_jointes']
    return document, 201


def _check_edit_access(participation_resource):
    # Only owner and admin can edit
    if (g.request_user['role'] != 'Administrateur' and
        g.request_user['_id'] != participation_resource['observateur']):
        abort(403)


def _check_read_access(participation_resource):
    owner = participation_resource['observateur']
    # If donnees_publiques, anyone can see
    # If not, only admin, validateur and owner can
    if (g.request_user['role'] == 'Administrateur' or
        g.request_user['role'] == 'Validateur' or
        g.request_user['_id'] == owner['_id']):
        return
    if not owner.get('donnees_publiques', False):
        abort(403)


def _check_add_message_access(participation_resource):
    # Administrateur, Validateur and owner are allowed
    if (g.request_user['role'] == 'Observateur' and
        g.request_user['_id'] != participation_resource['observateur']):
        abort(403)


@participations.route('/participations/<objectid:participation_id>', methods=['PATCH'])
@requires_auth(roles='Observateur')
def edit_participation(participation_id):
    participation_resource = participations.get_resource(participation_id)
    _check_edit_access(participation_resource)
    payload = get_payload({'date_debut': False, 'date_fin': False,
                           'commentaire': False, 'meteo': False,
                           'configuration': False})
    document = participations.update(participation_id, payload)
    if 'pieces_jointes' in document:
        del document['pieces_jointes']
    return document


@participations.route('/participations/<objectid:participation_id>/pieces_jointes', methods=['PUT'])
@requires_auth(roles='Observateur')
def add_pieces_jointes(participation_id):
    participation_resource = participations.get_resource(participation_id)
    _check_edit_access(participation_resource)
    payload = get_payload({'pieces_jointes': True})
    errors = {'pieces_jointes': []}
    if isinstance(payload['pieces_jointes'], list):
        for pj_id in payload['pieces_jointes']:
            pj = fichiers_resource.get_resource(pj_id, auto_abort=False)
            if not pj:
                errors['pieces_jointes'].append('bad id ' + pj_id)
            elif pj['mime'] not in ALLOWED_MIMES:
                errors['pieces_jointes'].append('file {} bad mime type '.format(pj_id))
            elif not pj.get('s3_upload_done', False):
                errors['pieces_jointes'].append('file {} upload is not done'.format(pj_id))
    if errors['pieces_jointes']:
        abort(422, errors)
    # If pieces_jointes is not a list, update's validation will throw error
    mongo_update = {'$push': {'pieces_jointes': {'$each': payload['pieces_jointes']}}}
    result = participations.update(participation_id, payload=payload,
                                   mongo_update=mongo_update)
    run_tadaridaD_on_participation.delay(result['_id'])
    return result


@participations.route('/participations/<objectid:participation_id>/pieces_jointes', methods=['GET'])
@requires_auth(roles='Observateur')
def get_pieces_jointes(participation_id):
    participation_resource = participations.find_one(participation_id)
    _check_read_access(participation_resource)
    pieces_jointes = participation_resource.get('pieces_jointes', [])
    return {'_items': pieces_jointes, '_meta': {'total': len(pieces_jointes)}}


@participations.route('/participations/<objectid:participation_id>/messages', methods=['PUT'])
@requires_auth(roles='Observateur')
def add_post(participation_id):
    participation_resource = participations.get_resource(participation_id)
    _check_add_message_access(participation_resource)
    new_message = {'auteur': g.request_user['_id'], 'date': datetime.utcnow(),
                   'message': get_payload({'message': True})['message']}
    payload = {'messages': [new_message]}
    mongo_update = {'$push': {'messages': {
                        '$each': payload['messages'],
                        '$position': 0
                    }}}
    return participations.update(participation_id, payload=payload,
                                 mongo_update=mongo_update)
