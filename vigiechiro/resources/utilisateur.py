"""
    Donnee utilisateur
    ~~~~~~~~~~~~~~~~~~

    see: https://scille.atlassian.net/wiki/pages/viewpage.action?pageId=13893760
"""

from flask import current_app, request, abort
import eve.auth
import eve.render
import eve.methods
from bson import ObjectId
from bson.errors import InvalidId

from ..xin import EveBlueprint
from ..xin.auth import requires_auth
from ..xin.domain import relation, choice


DOMAIN = {
    'item_title': 'utilisateur',
    'resource_methods': ['GET'],
    'item_methods': ['GET', 'PUT', 'PATCH'],
    'allowed_read_roles': ['Validateur'],
    'allowed_item_read_roles': ['Observateur'],
    'allowed_item_write_roles': ['Observateur'],
    'datasource': {
        # Private data : tokens list and login services' user id
        'projection': {'tokens': 0, 'github_id': 0,
                       'google_id': 0, 'facebook_id': 0}
    },
    'schema': {
        'github_id': {'type': 'string', 'writerights': 'Administrateur',
                      'unique': True},
        'google_id': {'type': 'string', 'writerights': 'Administrateur',
                      'unique': True},
        'facebook_id': {'type': 'string', 'writerights': 'Administrateur',
                      'unique': True},
        'pseudo': {'type': 'string', 'required': True},
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
                    'protocole': relation('protocoles', embeddable=True,
                                          utilisateur_validate_non_macro_protocole=True),
                    'valide': {'type': 'boolean', 'writerights': 'Administrateur'}
                }
            }
        }
    }
}
utilisateurs = EveBlueprint('utilisateurs', __name__, domain=DOMAIN,
                            auto_prefix=True)


@utilisateurs.validate
def utilisateur_validate_non_macro_protocole(self, validate, field, value):
    """Make sure the given value is a non macro protocole"""
    print(field, 'touill---->')
    if not validate:
        return
    try:
        protocole_id = ObjectId(value)
    except InvalidId:
        self._error(field, "value '{}' cannot be converted to a"
                           " ObjectId".format(protocole_id))
    protocoles_db = current_app.data.driver.db['protocoles']
    protocole = protocoles_db.find_one({'_id': protocole_id})
    if protocole:
        if protocole.get('macro_protocole', False):
            self._error(field, "cannot subscribe to a macro-protocole")
    else:
        self._error(field, "no protocoles with id {}".format(protocole_id))


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
    # Non-admin can modify it own account
    if ObjectId(lookup['_id']) != current_app.g.request_user['_id']:
        abort(403)


@utilisateurs.event
def on_pre_PUT(request, lookup):
    check_rights(request, lookup)


@utilisateurs.event
def on_pre_PATCH(request, lookup):
    check_rights(request, lookup)


@utilisateurs.event
def on_pre_GET(request, lookup):
    if '_id' in lookup:
        # Validateur and above can see other user's account
        if (ObjectId(lookup['_id']) != current_app.g.request_user['_id'] and
            current_app.g.request_user['role'] not in ['Administrateur', 'Validateur']):
            abort(403)
