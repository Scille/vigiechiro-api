from flask import current_app
from flask import app
from flask import abort, url_for, Blueprint, redirect
import eve.auth
import eve.endpoints
import eve.render

from .resource import Resource
# from ..action import eve_custom_route

from eve.utils import config, request_method, debug_error_message
import eve.methods
from flask import request, Response, g, abort
from functools import wraps


class Utilisateur(Resource):
    RESOURCE_NAME = 'utilisateurs'
    DOMAIN = {
        'item_title': 'utilisateur',
        'resource_methods': ['GET'],
        'item_methods': ['GET', 'PUT', 'PATCH'],
        'allowed_read_roles': ['Observateur'],
        'allowed_write_roles': ['Administrateur'],
        'allowed_item_read_roles': ['Observateur'],
        'allowed_item_write_roles': ['Observateur'],
        'datasource': {
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
            # Private data : tokens list
            'tokens': {
                'type': 'list',
                'schema': {'type': 'string'}
            }
        }
    }
    CONST_FIELDS = {'pseudo', 'email', 'role', 'tokens'}

    def __init__(self):
        super().__init__()
        @self.route('/utilisateurs/moi', methods=['GET', 'PUT', 'PATCH'], allowed_roles=['Observateur'])
        def route_moi():
            user_id = current_app.auth.get_request_auth_value()
            if user_id:
                if request.method in ('GET', 'HEAD'):
                    response = eve.methods.getitem(self.RESOURCE_NAME, _id=user_id)
                elif request.method == 'PATCH':
                    response = eve.methods.patch(self.RESOURCE_NAME, _id=user_id)
                elif request.method == 'PUT':
                    response = eve.methods.put(self.RESOURCE_NAME, _id=user_id)
                elif request.method == 'DELETE':
                    response = eve.methods.deleteitem(self.RESOURCE_NAME, _id=user_id)
                elif request.method == 'OPTIONS':
                    send_response(self.RESOURCE_NAME, response)
                else:
                    abort(405)
                return eve.render.send_response(self.RESOURCE_NAME, response)
            else:
                abort(404)
        @self.callback
        def on_pre_PUT(request, lookup):
            self._check_rights(request, lookup)
        @self.callback
        def on_pre_PATCH(request, lookup):
            self._check_rights(request, lookup)

    def _check_rights(self, request, lookup):
        if current_app.g.request_user['role'] == 'Administrateur':
            return
        # Non-admin can only modify it own account
        if lookup['_id'] != str(current_app.g.request_user['_id']):
            abort(403)
        # Not all field can be altered
        const_fields = set(request.json.keys()) & self.CONST_FIELDS
        if const_fields:
            abort(403, 'not allow to change field(s) {}'.format(const_fields))
