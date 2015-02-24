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
from ..xin.snippets import Paginator, get_resource, get_payload, get_lookup_from_q


SCHEMA = {
    'github_id': {'type': 'string', 'hidden': True, 'unique': True},
    'google_id': {'type': 'string', 'hidden': True, 'unique': True},
    'facebook_id': {'type': 'string', 'hidden': True, 'unique': True},
    'pseudo': {'type': 'string', 'required': True},
    'email': {'type': 'string', 'required': True, 'unique': True,
        'hidden': True
    },
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
        'hidden': True,
        'keyschema': {'type': 'datetime'}
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
    from .protocoles import protocoles as protocoles_resource
    for join in document['protocoles']:
        protocole_id = join['protocole']
        protocole = protocoles_resource.find_one(
            {'_id': protocole_id}, {'titre': 1})
        if protocole:
            join['protocole'] = protocole
    return document


def _hide_email(overwrite=None):
    """Hide email to everyone but current owner, administrateur and validateur"""
    if (overwrite == False or
        g.request_user.get('role', '') in ['Administrateur', 'Validateur']):
        return {'hidden': {'email': False}}
    else:
        return None


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
    found = utilisateurs.find(get_lookup_from_q(),
                               skip=pagination.skip,
                               limit=pagination.max_results,
                               additional_context=_hide_email())
    return pagination.make_response(*found)


@utilisateurs.route('/moi', methods=['GET'])
@requires_auth(roles='Observateur')
def get_request_user_profile():
    return utilisateurs.find_one(g.request_user['_id'],
                                 additional_context=_hide_email(False))


@utilisateurs.route('/utilisateurs/<objectid:user_id>', methods=['GET'])
@requires_auth(roles='Observateur')
def get_user_profile(user_id):
    return utilisateurs.find_one(user_id, additional_context=_hide_email())


def _utilisateur_patch(user_id, additional_context=None):
    allowed_fields = {'pseudo', 'email_publique', 'nom', 'prenom',
                      'telephone', 'adresse', 'commentaire', 'organisation',
                      'professionnel', 'donnees_publiques', 'email', 'role'}
    payload = get_payload(allowed_fields)
    result = utilisateurs.update(user_id, payload,
                                 additional_context=additional_context)
    return result


@utilisateurs.route('/moi', methods=['PATCH'])
@requires_auth(roles='Observateur')
def route_moi_patch():
    return _utilisateur_patch(g.request_user['_id'],
                              additional_context=_hide_email(False))


@utilisateurs.route('/utilisateurs/<objectid:user_id>', methods=['PATCH'])
@requires_auth(roles='Administrateur')
def route_utilisateur_patch(user_id):
    return _utilisateur_patch(user_id,
                              additional_context=_hide_email())
