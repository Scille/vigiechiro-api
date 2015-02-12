"""
    Resource utilisateurs
    ~~~~~~~~~~~~~~~~~~~~~

    see: https://scille.atlassian.net/wiki/pages/viewpage.action?pageId=13893760
"""

from flask import current_app, request, g
from bson import ObjectId
from bson.errors import InvalidId

from ..xin import Resource, preprocessor
from ..xin.tools import get_resource, jsonify, abort
from ..xin.auth import requires_auth
from ..xin.schema import relation, choice


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
        'writerights': 'Administrateur',
        'schema': {
            'type': 'dict',
            'schema': {
                'protocole': relation('protocoles', embeddable=True, required=True,
                                      non_macro_protocole=True),
                'date_inscription': {'type': 'datetime', 'required': True},
                'valide': {'type': 'boolean'}
            }
        }
    }
}

utilisateurs = Resource('utilisateurs', __name__, schema=SCHEMA)


DEFAULT_USER_PROJECTION = {'tokens': 0, 'github_id': 0,
                           'google_id': 0, 'facebook_id': 0,
                           'email': 0}
RESTRICTED_USER_PROJECTION = {'tokens': 0, 'github_id': 0,
                              'google_id': 0, 'facebook_id': 0}


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
    # Check params
    try:
        limit = int(request.args.get('max_results', 20))
        skip = (int(request.args.get('page', 1)) - 1) * limit
        if skip < 0:
            abort(422, 'page params must be > 0')
        if limit > 100:
            abort(422, 'max_results params must be < 100')
    except ValueError:
        abort(422, 'Invalid max_results and/or page params')
    bad_params = set(request.args.keys()) - {'page', 'max_results'}
    if bad_params:
        abort(422, 'Unknown params {}'.format(bad_params))
    db = current_app.data.db['utilisateurs']
    elements = list(db.find(None, DEFAULT_USER_PROJECTION, skip=skip, limit=limit))
    return jsonify({'_items': elements})


@utilisateurs.route('/utilisateurs/moi', methods=['GET'])
@requires_auth(roles='Observateur')
def get_request_user_profile():
    user = utilisateurs.get_resource(g.request_user['_id'],
                                     projection=RESTRICTED_USER_PROJECTION)
    return jsonify(**user)


@utilisateurs.route('/utilisateurs/<objectid:user_id>', methods=['GET'])
@requires_auth(roles='Observateur')
def get_user_profile(user_id):
    user = utilisateurs.get_resource(user_id, projection=DEFAULT_USER_PROJECTION)
    return jsonify(**user)


@utilisateurs.route('/utilisateurs/moi', methods=['PATCH'])
@requires_auth(roles='Observateur')
@preprocessor(if_match=True, payload=True)
def patch_request_user_profile(if_match, payload):
    allowed_fields = {'pseudo', 'email', 'email_publique', 'nom', 'prenom',
                      'telephone', 'adresse', 'commentaire', 'organisation',
                      'professionnel', 'donnees_publiques'}
    invalid_fields = set(payload.keys()) - allowed_fields
    if invalid_fields:
        abort(422, {field: 'invalid field' for field in invalid_fields})
    result = utilisateurs.update(g.request_user['_id'], payload, if_match)
    return jsonify(result)


@utilisateurs.route('/utilisateurs/<objectid:user_id>', methods=['PATCH'])
@requires_auth(roles='Administrateur')
@preprocessor(if_match=True, payload=True)
def patch_user(user_id, if_match, payload):
    result = utilisateurs.update(user_id, payload, if_match)
    return jsonify(result)
