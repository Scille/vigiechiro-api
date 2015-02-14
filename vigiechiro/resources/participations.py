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
from ..xin.snippets import get_payload, get_if_match, Paginator, get_resource

from .actualites import create_actuality_nouvelle_participation


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


participations = Resource('participations', __name__, schema=SCHEMA)


@participations.route('/participations', methods=['GET'])
@requires_auth(roles='Observateur')
def list_participations():
    pagination = Paginator()
    cursor = participations.find(skip=pagination.skip,
                                 limit=pagination.max_results)
    return pagination.make_response(cursor)


@participations.route('/moi/participations', methods=['GET'])
@requires_auth(roles='Observateur')
def list_user_participations():
    pagination = Paginator()
    cursor = participations.find({'observateur': g.request_user['_id']},
                                 skip=pagination.skip,
                                 limit=pagination.max_results)
    return pagination.make_response(cursor)


@participations.route('/participations/<objectid:participation_id>', methods=['GET'])
@requires_auth(roles='Observateur')
def display_participation(participation_id):
    return jsonify(**participations.get_resource(participation_id))


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
    inserted_payload = participations.insert(payload)
    # Finally create corresponding actuality
    create_actuality_nouvelle_participation(inserted_payload)
    return jsonify(**inserted_payload), 201


def _check_edit_access(participation_resource):
    # Only owner and admin can edit
    if (g.request_user['role'] != 'Administrateur' and
        g.request_user['_id'] != participation_resource['observateur']):
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
    inserted_payload = participations.update(participation_id, payload)
    return jsonify(**inserted_payload), 200


@participations.route('/participations/<objectid:participation_id>/pieces_jointes', methods=['POST'])
@requires_auth(roles='Observateur')
def add_pieces_jointes(participation_id):
    participation_resource = participations.get_resource(participation_id)
    _check_edit_access(participation_resource)
    payload = get_payload({'pieces_jointes': True})
    # TODO check files data type
    def custom_merge(document, payload):
        # Append data at the end of the list
        pieces = document.get('pieces_jointes', [])
        document['pieces_jointes'] = pieces + payload['pieces_jointes']
        return document
    inserted_payload = participations.update(participation_id, payload,
                                             custom_merge=custom_merge)
    return jsonify(**inserted_payload), 201


@participations.route('/participations/<objectid:participation_id>/messages', methods=['POST'])
@requires_auth(roles='Observateur')
def add_post(participation_id):
    participation_resource = participations.get_resource(participation_id)
    _check_add_message_access(participation_resource)
    payload = {'messages': [
        {'auteur': g.request_user['_id'], 'date': datetime.utcnow(),
         'message': get_payload({'message': True})['message']}
    ]}
    def custom_merge(document, payload):
        # Append data at the beginning of the list
        previous_messages = document.get('messages', [])
        document['messages'] = [payload['messages']] + previous_messages
        return document
    inserted_payload = participations.update(participation_id, payload,
                                             custom_merge=custom_merge)
    return jsonify(**inserted_payload), 201
