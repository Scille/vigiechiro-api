"""
    Donnee protocoles
    ~~~~~~~~~~~~~~~~~

    see: https://scille.atlassian.net/wiki/pages/viewpage.action?pageId=13893673
"""

from flask import g
from datetime import datetime

from ..xin import Resource
from ..xin.tools import jsonify, abort, dict_projection
from ..xin.auth import requires_auth
from ..xin.schema import relation, choice
from ..xin.snippets import get_payload, get_if_match, Paginator

from .actualites import create_actuality_validation_protocole, create_actuality_inscription_protocole


SCHEMA = {
    'titre': {'type': 'string', 'required': True},
    'description': {'type': 'string'},
    'parent': relation('protocoles'),
    'macro_protocole': {'type': 'boolean'},
    'tags': {
        'type': 'list',
        'schema': {'type': 'string'}
    },
    'fichiers': {
        'type': 'list',
        'schema': relation('fichiers', required=True),
    },
    'type_site': choice(['LINEAIRE', 'POLYGONE'], required=True),
    'taxon': relation('taxons', required=True),
    'configuration_participation': {
        'type': 'list',
        'schema': {'type': 'string'}
    },
    'algo_tirage_site': choice(['CARRE', 'ROUTIER', 'POINT_FIXE'], required=True)
}


protocoles = Resource('protocoles', __name__, schema=SCHEMA)


def check_configuration_participation(payload):
    """
        Make sure the configuration provided is compatible with the data model
        of the participation
    """
    if 'configuration_participation' not in payload:
        return
    # TODO replace by real config list
    # participation_configuration_fields = participations.get_configuration_fields()
    participation_configuration_fields = [
        'detecteur_enregistreur_numero_serie',
        'micro0_position',
        'micro0_numero_serie',
        'micro0_hauteur',
        'micro1_position',
        'micro1_numero_serie',
        'micro1_hauteur']
    bad_keys = [key for key in payload['configuration_participation']
                if key not in participation_configuration_fields]
    if bad_keys:
        abort(422, "configuration_participation fields {}"
                   " are not valid".format(bad_keys))


@protocoles.route('/protocoles', methods=['GET'])
@requires_auth(roles='Observateur')
def list_protocoles():
    pagination = Paginator()
    found = protocoles.find(skip=pagination.skip, limit=pagination.max_results)
    return pagination.make_response(*found)


@protocoles.route('/moi/protocoles', methods=['GET'])
@requires_auth(roles='Observateur')
def list_user_protocoles():
    pagination = Paginator()
    joined_ids = [p['protocole'] for p in g.request_user.get('protocoles', [])]
    found = protocoles.find({'_id': {'$in': joined_ids}},
                             skip=pagination.skip, limit=pagination.max_results)
    return pagination.make_response(*found)


@protocoles.route('/protocoles', methods=['POST'])
@requires_auth(roles='Administrateur')
def create_protocole():
    payload = get_payload()
    check_configuration_participation(payload)
    inserted_payload = protocoles.insert(payload)
    return jsonify(inserted_payload), 201


@protocoles.route('/protocoles/<objectid:protocole_id>', methods=['GET'])
@requires_auth(roles='Observateur')
def display_protocole(protocole_id):
    return jsonify(**protocoles.get_resource(protocole_id))


@protocoles.route('/protocoles/<objectid:protocole_id>', methods=['PATCH'])
@requires_auth(roles='Administrateur')
def edit_protocole(protocole_id):
    payload = get_payload()
    check_configuration_participation(payload)
    result = protocoles.update(protocole_id, payload, get_if_match())
    return jsonify(result)


@protocoles.route('/protocoles/liste', methods=['GET'])
@requires_auth(roles='Observateur')
def get_resume_list():
    """Return a brief list of per protocole id and libelle"""
    items = protocoles.find({}, {"libelle_long": 1})
    return jsonify(_items=[i for i in items])


@protocoles.route('/protocoles/<objectid:protocole_id>/join', methods=['POST'])
@requires_auth(roles='Observateur')
def user_join_protocole(protocole_id):
    """Register the request user to the given protocole"""
    from .utilisateurs import utilisateurs as utilisateurs_resource, get_payload_add_following
    # Check if the user already joined the protocole
    joined_protocoles = g.request_user.get('protocoles', [])
    if next((p for p in joined_protocoles
             if p['protocole'] == protocole_id), None):
        abort(422, "user already registered in protocole {}".format(protocole_id))
    protocole_resource = protocoles.get_resource(protocole_id)
    # Cannot join a macro protocole
    if protocole_resource.get('macro_protocole', False):
        abort(422, "Cannot join a macro protocole")
    # Update user's protocole list
    inscription = {'protocole': protocole_id,
                   'date_inscription': datetime.utcnow(),
                   'valide': False}
    joined_protocoles.append(inscription)
    payload = {'protocoles': joined_protocoles}
    # User automatically follow the protocole
    payload.update(get_payload_add_following(protocole_id))
    utilisateurs_resource.update(g.request_user['_id'], payload)
    # Finally create corresponding actuality
    create_actuality_inscription_protocole(protocole_resource, g.request_user)
    return jsonify(**inscription)


@protocoles.route('/protocoles/<objectid:protocole_id>/observateurs/<objectid:user_id>', methods=['PUT'])
@requires_auth(roles='Administrateur')
def user_validate_protocole(protocole_id, user_id):
    """Validate a user into a protocole"""
    from .utilisateurs import utilisateurs as utilisateurs_resource
    payload = get_payload({'valide'})
    user_resource = utilisateurs_resource.get_resource(user_id)
    # Make sure the user has joined the protocole and is not valid yet
    joined_protocoles = user_resource.get('protocoles', [])
    to_validate_protocole = next((p for p in joined_protocoles
                                  if p['protocole'] == protocole_id), None)
    if not to_validate_protocole:
        abort(422, 'user {} has not joined protocole {}'.format(
            user_id, protocole_id))
    if to_validate_protocole.get('valide', False):
        abort(422, 'user {} has already been validated into protocole {}'.format(
            user_id, protocole_id))
    # Finally update user's protocole status
    to_validate_protocole['valide'] = payload['valide']
    utilisateurs_resource.update(user_id, {'protocoles': joined_protocoles})
    # Finally create corresponding actuality
    create_actuality_validation_protocole({'_id': protocole_id}, g.request_user)
    return jsonify(**to_validate_protocole)
