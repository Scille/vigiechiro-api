from flask import current_app, request, abort
import eve.auth
import eve.render
import eve.methods
from bson import ObjectId
from bson.errors import InvalidId

from vigiechiro.xin import EveBlueprint
from vigiechiro.xin.auth import requires_auth
from .resource import relation


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
        'pseudo': {
            'type': 'string', 'postonly': True,
            'unique': True, 'required': True
        },
        'email': {'type': 'string', 'postonly': True, 'required': True, 'unique': True},
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
        'role': {'type': 'string', 'writerights': 'Administrateur'},
        'tags': {
            'type': 'list',
            'schema': {'type': 'string'}
        },
        'tokens': {
            'type': 'list',
            'schema': {'type': 'string', 'writerights': 'Administrateur'}
        },
        'protocoles': {
            'type': 'dict',
            'utilisateur_validate_protocoles': True,
            'keyschema': {
                'type': 'dict',
                'schema': {'valide': {'type': 'boolean', 'writerights': 'Administrateur'}}
            }
        }
    }
}
utilisateurs = EveBlueprint('utilisateurs', __name__, domain=DOMAIN,
                            auto_prefix=True)


@utilisateurs.validate
def utilisateur_validate_protocoles(self, validate, field, value):
    """Make sure each key in the `protocoles` dict is a valid relation"""
    if validate:
        protocoles_db = current_app.data.driver.db['protocoles']
        error_msg = "value '{}' cannot be converted to a ObjectId"
        for protocole_id in value.keys():
            try:
                protocole_id = ObjectId(protocole_id)
                protocole = protocoles_db.find_one({'_id': protocole_id})
                if protocole:
                    if protocole.get('macro_protocole', False):
                        self._error(
                            field,
                            'cannot subscribe to a macro-protocole')
                else:
                    self._error(
                        field,
                        'no protocoles with id {}'.format(protocole_id))
            except InvalidId:
                self._error(field, error_msg.format(protocole_id))


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


@utilisateurs.event
def on_pre_PUT(request, lookup):
    check_rights(request, lookup)


@utilisateurs.event
def on_pre_PATCH(request, lookup):
    check_rights(request, lookup)
