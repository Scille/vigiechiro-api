"""
    Donnee protocoles
    ~~~~~~~~~~~~~~~~~

    see: https://scille.atlassian.net/wiki/pages/viewpage.action?pageId=13893673
"""

from flask import g, request
from datetime import datetime

from ..xin import Resource
from ..xin.tools import jsonify, abort, dict_projection
from ..xin.auth import requires_auth
from ..xin.schema import relation, choice
from ..xin.snippets import (Paginator, get_lookup_from_q, get_payload,
                            get_if_match, get_url_params)

from .actualites import (create_actuality_validation_protocole,
                         create_actuality_inscription_protocole_batch,
                         create_actuality_reject_protocole)
from .utilisateurs import (utilisateurs as utilisateurs_resource,
                           get_payload_add_following)


SCHEMA = {
    'titre': {'type': 'string', 'required': True},
    'description': {'type': 'string'},
    'parent': relation('protocoles'),
    'macro_protocole': {'type': 'boolean'},
    'autojoin': {'type': "boolean"},
    'tags': {
        'type': 'list',
        'schema': {'type': 'string'}
    },
    'fichiers': {
        'type': 'list',
        'schema': relation('fichiers', required=True),
    },
    'taxon': relation('taxons', required=True),
    'configuration_participation': {
        'type': 'list',
        'schema': {'type': 'string'}
    },
    'type_site': choice(['CARRE', 'ROUTIER', 'POINT_FIXE'])
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
    found = protocoles.find(get_lookup_from_q(), skip=pagination.skip,
                            limit=pagination.max_results)
    return pagination.make_response(*found)


@protocoles.route('/moi/protocoles', methods=['GET'])
@requires_auth(roles='Observateur')
def list_user_protocoles():
    pagination = Paginator()
    joined_ids = [p['protocole'] for p in g.request_user.get('protocoles', [])]
    found = protocoles.find({'_id': {'$in': joined_ids}},
                            skip=pagination.skip, limit=pagination.max_results)
    return pagination.make_response(*found)


def _check_macro_protocole_type_site(payload):
    if payload.get('macro_protocole', False):
        if payload.get('type_site', None):
            abort(422, {'type_site': 'macro protocole should not contain a type_site'})
        if payload.get('autojoin', None):
            abort(422, {'type_site': 'macro protocole cannot be autojoined'})
    else:
        if not payload.get('type_site', None):
            abort(422, {'type_site': 'non macro protocole must contain a type_site'})


@protocoles.route('/protocoles', methods=['POST'])
@requires_auth(roles='Administrateur')
def create_protocole():
    payload = get_payload()
    _check_macro_protocole_type_site(payload)
    check_configuration_participation(payload)
    inserted_payload = protocoles.insert(payload)
    return inserted_payload, 201


@protocoles.route('/protocoles/<objectid:protocole_id>', methods=['GET'])
@requires_auth(roles='Observateur')
def display_protocole(protocole_id):
    return protocoles.find_one({'_id': protocole_id})


@protocoles.route('/protocoles/<objectid:protocole_id>', methods=['PATCH'])
@requires_auth(roles='Administrateur')
def edit_protocole(protocole_id):
    payload = get_payload()
    if payload.get('macro_protocole') is not None:
        _check_macro_protocole_type_site(payload)
    check_configuration_participation(payload)
    result = protocoles.update(protocole_id, payload, if_match=get_if_match())
    return jsonify(result)


@protocoles.route('/protocoles/<objectid:protocole_id>/observateurs', methods=['GET'])
@requires_auth(roles='Observateur')
def list_protocole_users(protocole_id):
    lookup = {'protocoles.protocole': protocole_id}
    pagination = Paginator()
    val_type = get_url_params({'protocole': False, 'type': False}).get('type', 'TOUS')
    if val_type == 'A_VALIDER':
        lookup['protocoles.valide'] = {'$ne': True}
    elif val_type == 'VALIDES':
        lookup['protocoles.valide'] = True
    elif val_type != 'TOUS':
        abort(422, {'type': 'bad param type'})
    found = utilisateurs_resource.find(lookup or None,
                                       skip=pagination.skip,
                                       limit=pagination.max_results)
    return pagination.make_response(*found)


@protocoles.route('/protocoles/liste', methods=['GET'])
@requires_auth(roles='Observateur')
def get_resume_list():
    """Return a brief list of per protocole id and libelle"""
    items = protocoles.find({}, {"libelle_long": 1})
    return jsonify(_items=[i for i in items])


def get_default_protocoles():
    return protocoles.find({'autojoin': True})[0]


def do_user_join_protocoles(user_id, protocoles, inscription_validee=False):
    now = datetime.utcnow()
    inscriptions = [
        {'protocole': protocole_id,
        'date_inscription': now,
        'valide': inscription_validee}
        for protocole_id in protocoles
    ]
    payload = {'protocoles': inscriptions}
    # User automatically follow the protocole
    mongo_update = {
        '$push': {'protocoles': {'$each': inscriptions}},
        '$addToSet': {'actualites_suivies': {'$each': protocoles}}
    }
    user = utilisateurs_resource.update(
        user_id,
        mongo_update=mongo_update,
        payload=payload
    )
    # Finally create corresponding actuality
    create_actuality_inscription_protocole_batch(user_id, protocoles, inscription_validee=inscription_validee)
    return user, inscriptions


@protocoles.route('/moi/protocoles/<objectid:protocole_id>', methods=['PUT'])
@requires_auth(roles='Observateur')
def user_join_protocole(protocole_id):
    """Register the request user to the given protocole"""
    # Check if the user already joined the protocole
    joined_protocoles = g.request_user.get('protocoles', [])
    if next((p for p in joined_protocoles
             if p['protocole'] == protocole_id), None):
        abort(422, "user already registered in protocole {}".format(protocole_id))
    protocole_resource = protocoles.get_resource(protocole_id)
    # Cannot join a macro protocole
    if protocole_resource.get('macro_protocole', False):
        abort(422, "Cannot join a macro protocole")
    # Autovalidation for admin
    inscription_validee = g.request_user['role'] == 'Administrateur'
    user_id = g.request_user['_id']
    _, (inscription, *_) = do_user_join_protocoles(user_id, [protocole_id], inscription_validee=inscription_validee)
    return jsonify(**inscription)


@protocoles.route('/protocoles/<objectid:protocole_id>/observateurs/<objectid:user_id>', methods=['PUT'])
@requires_auth(roles='Administrateur')
def user_validate_protocole(protocole_id, user_id):
    """Validate a user into a protocole"""
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
    lookup = {'_id': user_id, 'protocoles.protocole': protocole_id}
    # Validate observateur
    mongo_update = {'$set': {'protocoles.$.valide': True}}
    to_validate_protocole['valide'] = True
    payload = {'protocoles': [to_validate_protocole]}
    # Finally update user's protocole status
    utilisateurs_resource.update(lookup, mongo_update=mongo_update, payload=payload)
    # Finally create corresponding actuality
    create_actuality_validation_protocole({'_id': protocole_id}, user_resource)
    return to_validate_protocole


@protocoles.route('/protocoles/<objectid:protocole_id>/observateurs/<objectid:user_id>', methods=['DELETE'])
@requires_auth(roles='Administrateur')
def user_reject_protocole(protocole_id, user_id):
    """Remove a user from a protocole"""
    user_resource = utilisateurs_resource.get_resource(user_id)
    # Make sure the user has joined the protocole and is not valid yet
    joined_protocoles = user_resource.get('protocoles', [])
    to_validate_protocole = next((p for p in joined_protocoles
                                  if p['protocole'] == protocole_id), None)
    if not to_validate_protocole:
        abort(422, 'user {} has not joined protocole {}'.format(
            user_id, protocole_id))
    lookup = {'_id': user_id}
    # Remove protocle from observateur
    mongo_update = {'$pull': {'protocoles': {'protocole': protocole_id}}}
    payload = {'protocoles': []}
    # Finally update user's protocole status
    utilisateurs_resource.update(lookup, mongo_update=mongo_update, payload=payload)
    # Finally create corresponding actuality
    create_actuality_reject_protocole({'_id': protocole_id}, user_resource)
    return to_validate_protocole
