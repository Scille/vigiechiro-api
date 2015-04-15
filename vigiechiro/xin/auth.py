#! /usr/bin/env python3

import random
import base64
import logging
import string
import types
from functools import wraps
from datetime import datetime, timedelta
import bson
from uuid import uuid4

from flask import Blueprint, redirect, g, Response
from flask import app, current_app, request, abort
from authomatic.extras.flask import FlaskAuthomatic

from .tools import jsonify
from .. import settings


def get_request_user():
    """Return the current user or an empty dict if anonymous user"""
    return g.request_user if hasattr(g, request_user) else {}


def check_auth(token, allowed_roles):
    """
        Token-based authentication with role filtering
        Once user profile has been retrieved from the given token,
        it is stored in application context as **g.request_user**::

            from flask import app, request, jsonify
            @app.route('/my_profile')
            def my_profile():
                # Token-based auth is provided as username and empty password
                check_auth(request.authorization.username, ['admin'])
                # Return the user profile
                return jsonify(g.request_user)
    """
    accounts = current_app.data.db['utilisateurs']
    account = accounts.find_one({'tokens.{}'.format(token): {'$exists': True}})
    if account:
        if account['tokens'][token] < datetime.now(bson.utc):
            # Out of date token
            return False
        if allowed_roles:
            # Role are handled using least privilege, thus a higher
            # privileged role also include it lower roles.
            role = account['role']
            if not next((True for r in current_app.config['ROLE_RULES'][role]
                         if r in allowed_roles), False):
                abort(403)
        # Keep request user account in local context, could be useful later
        g.request_user = account
        return True
    return False


def requires_auth(roles=[]):
    """
        A decorator to check if the current user (identified by the
        given token) has the correct role to access the decorated function
    """
    roles = [roles] if isinstance(roles, str) else roles

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.authorization
            if not auth or not check_auth(auth.username, roles):
                # Returns a 401 that enables basic auth
                resp = Response(None, 401, {'WWW-Authenticate': 'Basic realm:"%s"' % __package__})
                abort(401, description='Please provide proper credentials', response=resp)
            return f(*args, **kwargs)
        return decorated
    return decorator


def auth_factory(services, mock_provider=False):
    """Generate flask blueprint of login endpoints
       :params services: list of services to generate endpoints
       :params mock_provider: simulate auth provider (NO ACTUAL AUTH IS DONE !)

       >>> from flask import Flask
       >>> from vigiechiro.xin.auth import auth_factory
       >>> f = Flask('test')
       >>> blueprint = auth_factory(['github', 'google'])
       >>> f.register_blueprint(blueprint)
       >>> [url.rule for url in f.url_map.iter_rules()]
       ['/login/github', '/login/google', '/logout', '/static/<path:filename>']
    """
    authomatic = FlaskAuthomatic(config=settings.AUTHOMATIC,
                                 secret=settings.SECRET_KEY)
    auth_blueprint = Blueprint('auth', __name__)

    if mock_provider:
        class MockClass: pass
        def login_factory(service):
            user = MockClass()
            user.__dict__ = {'id': '123456789',
                             'email': 'mock_user@{}.com'.format(service),
                             'name': 'John Doe'}
            user.__dict__['update'] = lambda: None
            result = MockClass()
            result.__dict__ = {'user': user, 'error': {}}
            mock_authomatic = MockClass()
            mock_authomatic.__dict__ = {'result': result}
            return lambda: login(mock_authomatic, service)
    else:
        def login_factory(service):
            return authomatic.login(service)(lambda: login(authomatic, service))
    for service in services:
        auth_blueprint.add_url_rule('/login/' + service, 'login_' + service,
                                    login_factory(service))

    @auth_blueprint.route('/logout', methods=['OPTIONS', 'POST'])
    @requires_auth()
    def logout():
        if request.authorization:
            token = request.authorization['username']
            users = current_app.data.db['utilisateurs']
            token_field = 'tokens.{}'.format(token)
            lookup = {token_field: {'$exists': True}}
            result = users.update(lookup, {'$unset': {token_field: ""}})
            if not result['n']:
                abort(404)
            logging.info('Destroying token {}'.format(token))
        return jsonify({'_status': 'Disconnected'})
    return auth_blueprint


def login(authomatic, provider_name):
    """Login/user register endpoint using authomatic for the heavy lifting"""
    if authomatic.result:
        if authomatic.result.error:
            # It is most likely the client cancel it login request,
            # just reroute him to the website
            return redirect(current_app.config['FRONTEND_DOMAIN'], code=302)
        elif authomatic.result.user:
            authomatic.result.user.update()
            # Register the user
            new_token = ''.join(random.choice(string.ascii_uppercase +
                                              string.digits) for x in range(32))
            new_token_expire = (datetime.utcnow() +
                timedelta(seconds=current_app.config['TOKEN_EXPIRE_TIME']))
            user = authomatic.result.user
            provider_id_name = provider_name + '_id'
            # Lookup for existing user by email and provider id
            users_db = current_app.data.db['utilisateurs']
            document = users_db.find_one(
                {'$or': [{'email': user.email}, {provider_id_name: user.id}]})
            new_etag = uuid4().hex
            new_updated = datetime.utcnow().replace(microsecond=0)
            if document:
                # Add the new token and check expire date for existing ones
                mongo_update = {'$set': {
                                    'tokens.{}'.format(new_token): new_token_expire,
                                    provider_id_name: user.id,
                                    '_etag': new_etag,
                                    '_updated': new_updated}
                               }
                now = datetime.now(bson.utc)
                unset = []
                for token, token_expire in document.get('tokens', {}).items():
                    if now > token_expire:
                        unset.append(token)
                if unset:
                    mongo_update['$unset'] = {'tokens.{}'.format(t): True for t in unset}
                users_db.update({'_id': document['_id']}, mongo_update)
            else:
                # Creating a new utilisateur resource
                user_payload = {
                    provider_id_name: user.id,
                    '_created': new_updated,
                    '_updated': new_updated,
                    '_etag': new_etag,
                    'pseudo': user.name,
                    'email': user.email,
                    'tokens': {new_token: new_token_expire},
                    'role': 'Observateur',
                    'donnees_publiques': True
                }
                users_db.insert(user_payload)
                logging.info('Create new user : {}'.format(user.email))
            return redirect('{}/#/?token={}'.format(
                current_app.config['FRONTEND_DOMAIN'], new_token), code=302)
    else:
        return authomatic.response


if __name__ == "__main__":
    import doctest
    doctest.testmod()
