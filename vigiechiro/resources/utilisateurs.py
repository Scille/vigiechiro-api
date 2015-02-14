"""
    Resource utilisateurs
    ~~~~~~~~~~~~~~~~~~~~~

    see: https://scille.atlassian.net/wiki/pages/viewpage.action?pageId=13893760
"""

from flask import current_app, request, g, abort
from bson import ObjectId
from bson.errors import InvalidId

from ..xin import Resource
from ..xin.tools import jsonify, dict_projection
from ..xin.auth import requires_auth
from ..xin.schema import relation, choice
from ..xin.snippets import get_resource, Paginator, get_if_match, get_payload
from .protocoles import protocoles as protocoles_resource


SCHEMA = {
    'github_id': {'type': 'string', 'writerights': 'Administrateur',
                  'unique': True},
    'google_id': {'type': 'string', 'writerights': 'Administrateur',
                  'unique': True},
    'facebook_id': {'type': 'string', 'writerights': 'Administrateur',
                  'unique': True},
    'pseudo': {'type': 'string', 'required': True},
    'email': {'type': 'string', 'required': True, 'unique': True},
    'email_public': {'type': 'string', 'unique': True},
    'nom': {'type': 'string'},
    'prenom': {'type': 'string'},
    'telephone': {'type': 'string'},
    'adresse': {'type': 'string'},
    'commentaire': {'type': 'string'},
    'organisation': {'type': 'string'},
    'tag': {
        'type': 'list',
        'schema': {'type': 'string'}
    },
    'professionnel': {'type': 'boolean'},
    'donnees_publiques': {'type': 'boolean'},
    'role': choice(['Administrateur', 'Validateur', 'Observateur'],
                   writerights='Administrateur'),
    'tags': {
        'type': 'list',
        'schema': {'type': 'string'}
    },
    'tokens': {
        'type': 'dict',
        'writerights': 'Administrateur',
        'keyschema': {'type': 'datetime', 'writerights': 'Administrateur'}
    },
    'protocoles': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'protocole': relation('protocoles', required=True,
                                      non_macro_protocole=True),
                'date_inscription': {'type': 'datetime', 'required': True},
                'valide': {'type': 'boolean'}
            }
        }
    },
    'actualites_suivies': {
        'type': 'set',
        'schema': {'type': 'objectid'}
    }
}

DEFAULT_USER_PROJECTION = {
    'tokens': 0, 'github_id': 0,
    'google_id': 0, 'facebook_id': 0,
    'email': 0
}

RESTRICTED_USER_PROJECTION = {
    'tokens': 0, 'github_id': 0,
    'google_id': 0, 'facebook_id': 0
}


utilisateurs = Resource('utilisateurs', __name__, schema=SCHEMA)


def get_payload_add_following(ids):
    ids = {ids} if not isinstance(ids, list) else ids
    actualites_suivies = set(g.request_user.get('actualites_suivies', []))
    if not ids - actualites_suivies:
        # No new following
        return {}
    payload = {'actualites_suivies': actualites_suivies | ids}
    return payload


def _expend_joined_protocoles(document):
    if 'protocoles' not in document:
        return document
    for join in document['protocoles']:
        protocole_id = join['protocole']
        protocole = protocoles_resource.find_one(
            {'_id': protocole_id}, {'titre': 1})
        if protocole:
            join['protocole'] = protocole
    return document


def _choose_utilisateur_projection():
    if g.request_user['role'] == 'Observateur':
        return DEFAULT_USER_PROJECTION
    else:
        return RESTRICTED_USER_PROJECTION


@utilisateurs.validator.attribute
def non_macro_protocole(context):
    """Make sure the given value is a non macro protocole"""
    if not context.schema['non_macro_protocole']:
        return
    protocole = get_resource('protocoles', context.value, auto_abort=False)
    if not protocole:
        context.add_error("no protocoles with id {}".format(protocole_id))
    elif protocole.get('macro_protocole', False):
        context.add_error("cannot subscribe to a macro-protocole")


@utilisateurs.route('/utilisateurs', methods=['GET'])
@requires_auth(roles='Observateur')
def list_users():
    pagination = Paginator()
    cursor = utilisateurs.find(None, _choose_utilisateur_projection(),
                               skip=pagination.skip,
                               limit=pagination.max_results)
    return pagination.make_response(cursor)


@utilisateurs.route('/moi', methods=['GET'])
@requires_auth(roles='Observateur')
def get_request_user_profile():
    user = utilisateurs.get_resource(g.request_user['_id'],
                                     projection=RESTRICTED_USER_PROJECTION)
    return jsonify(**_expend_joined_protocoles(user))


@utilisateurs.route('/utilisateurs/<objectid:user_id>', methods=['GET'])
@requires_auth(roles='Observateur')
def get_user_profile(user_id):
    user = utilisateurs.get_resource(user_id,
        projection=_choose_utilisateur_projection())
    return jsonify(**_expend_joined_protocoles(user))


@utilisateurs.route('/moi', methods=['PATCH'])
@requires_auth(roles='Observateur')
def patch_request_user_profile():
    allowed_fields = {'pseudo', 'email_publique', 'nom', 'prenom',
                      'telephone', 'adresse', 'commentaire', 'organisation',
                      'professionnel', 'donnees_publiques', 'email'}
    payload = get_payload(allowed_fields)
    result = utilisateurs.update(g.request_user['_id'], payload, get_if_match())
    return jsonify(dict_projection(result, RESTRICTED_USER_PROJECTION))


@utilisateurs.route('/utilisateurs/<objectid:user_id>', methods=['PATCH'])
@requires_auth(roles='Administrateur')
def patch_user(user_id):
    allowed_fields = {'pseudo', 'email_publique', 'nom', 'prenom',
                      'telephone', 'adresse', 'commentaire', 'organisation',
                      'professionnel', 'donnees_publiques', 'email', 'role'}
    payload = get_payload()
    result = utilisateurs.update(user_id, payload, get_if_match())
    return jsonify(dict_projection(result, RESTRICTED_USER_PROJECTION))
