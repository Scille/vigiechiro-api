from flask import current_app, request, abort
import eve.auth
import eve.render
import eve.methods
from bson import ObjectId

from vigiechiro.xin import EveBlueprint
from vigiechiro.xin.auth import requires_auth
from .resource import Resource, relation


DOMAIN = {
    'item_title': 'utilisateur',
    'resource_methods': ['GET'],
    'item_methods': ['GET', 'PUT', 'PATCH'],
    'allowed_item_read_roles': ['Observateur'],
    'allowed_item_write_roles': ['Observateur'],
    'datasource': {
        # Private data : tokens list
        'projection': {'tokens': 0}
    },
    'schema': {
        'pseudo': {'type': 'string', 'required': True, 'unique': True},
        'email': {'type': 'string', 'required': True, 'unique': True},
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
        'role': {
            'type': 'string',
        },
        'tags': {
            'type': 'list',
            'schema': {'type': 'string'}
        },
        'tokens': {
            'type': 'list',
            'schema': {'type': 'string'}
        },
        'protocoles': {
            'type': 'list',
            'schema': {
                'valide': {'type': 'boolean'},
                'protocole': relation('protocoles', required=True)
            }
        }
    }
}
CONST_FIELDS = {'pseudo', 'email', 'role', 'tokens'}
utilisateurs = EveBlueprint('utilisateurs', __name__, domain=DOMAIN,
                            url_prefix='/utilisateurs')


@utilisateurs.route('/moi', methods=['GET', 'PUT', 'PATCH'])
@requires_auth(roles='Observateur')
def route_moi():
    user_id = current_app.g.request_user['_id']
    if user_id:
        if request.method in ('GET', 'HEAD'):
            response = eve.methods.getitem('utilisateurs', _id=user_id)
        elif request.method == 'PATCH':
            response = eve.methods.patch('utilisateurs', _id=user_id)
        elif request.method == 'PUT':
            response = eve.methods.put('utilisateurs', _id=user_id)
        elif request.method == 'DELETE':
            response = eve.methods.deleteitem('utilisateurs', _id=user_id)
        elif request.method == 'OPTIONS':
            send_response('utilisateurs', response)
        else:
            abort(405)
        return eve.render.send_response('utilisateurs', response)
    else:
        abort(404)


def check_rights(request, lookup):
    if current_app.g.request_user['role'] == 'Administrateur':
        return
    # Non-admin can only modify it own account
    if ObjectId(lookup['_id']) != current_app.g.request_user['_id']:
        abort(403)
    # Not all fields can be altered
    const_fields = set(request.json.keys()) & CONST_FIELDS
    if const_fields:
        abort(403, 'not allowed to alter field(s) {}'.format(const_fields))


@utilisateurs.event
def on_pre_PUT_utilisateurs(request, lookup):
    check_rights(request, lookup)


@utilisateurs.event
def on_pre_PATCH_utilisateurs(request, lookup):
    check_rights(request, lookup)
