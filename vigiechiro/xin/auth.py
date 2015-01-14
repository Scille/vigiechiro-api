#! /usr/bin/env python3

import random
import base64
import logging
import string
import types
from functools import wraps
from datetime import datetime, timedelta
import bson

from flask import Blueprint, redirect
from flask import app, current_app, abort, request
import eve.auth
import eve.render
from eve.methods.post import post_internal
from authomatic.extras.flask import FlaskAuthomatic

from .. import settings


def check_auth(token, allowed_roles):
    """
        Token-based authentification with role filtering
        Once user profile has been retrieved from the given token,
        it is stored in application context as **current_app.g.request_user**::

            from flask import app, request, jsonify
            @app.route('/my_profile')
            def my_profile():
                # Token-based auth is provided as username and empty password
                check_auth(request.authorization.username, ['admin'])
                # Return the user profile
                return jsonify(current_app.g.request_user)
    """
    accounts = current_app.data.driver.db['utilisateurs']
    account = accounts.find_one({'tokens.{}'.format(token): {'$exists': True}})
    if account:
        if account['tokens'][token] < datetime.now(bson.utc):
            # Out of date token
            return False
        if allowed_roles:
            # Role are handled using least priviledge, thus a higher
            # priviledged role also include it lower roles.
            role = account['role']
            if not next((True for r in current_app.config['ROLE_RULES'][role]
                         if r in allowed_roles), False):
                abort(403)
        # Keep request user account in local context, could be useful later
        current_app.g.request_user = account
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
                return current_app.auth.authenticate()
            return f(*args, **kwargs)
        return decorated
    return decorator


class TokenAuth(eve.auth.TokenAuth):

    """Custom token & roles authentification for Eve"""

    def check_auth(self, token, allowed_roles, resource, method):
        if check_auth(token, allowed_roles):
            current_app.set_request_auth_value(
                current_app.g.request_user['_id'])
            return True
        else:
            return False


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
            users = current_app.data.driver.db['utilisateurs']
            token_field = 'tokens.{}'.format(token)
            lookup = {token_field: {'$exists': True}}
            result = users.update(lookup, {'$unset': {token_field: ""}})
            if not result['n']:
                abort(404)
            logging.info('Destroying token {}'.format(token))
        return eve.render.send_response(None, [])
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
            users_db = current_app.data.driver.db['utilisateurs']
            user = authomatic.result.user
            provider_id_name = provider_name + '_id'
            user_db = users_db.find_one({'email': user.email})
            if user_db:
                # Add the new token and check expire date for existing ones
                tokens = {new_token: new_token_expire}
                now = datetime.now(bson.utc)
                for token, token_expire in user_db['tokens'].items():
                    if now < token_expire:
                        tokens[token] = token_expire
                users_db.update({'email': user.email},
                                {"$set": {provider_id_name: user.id,
                                          'tokens': tokens}})
            else:
                # We must switch to admin mode to insert a new user
                current_app.g.request_user = {'role': 'Administrateur'}
                user_payload = {
                    provider_id_name: user.id,
                    'pseudo': user.name,
                    # TODO fix github email
                    'email': (user.email or
                        ''.join(random.choice(string.ascii_uppercase + string.digits)
                                for x in range(10)) + '@fixmegithub.com'),
                    'tokens': {new_token: new_token_expire},
                    'role': 'Observateur'
                }
                result = post_internal('utilisateurs', user_payload)
                # Drop admin right for security
                del current_app.g.request_user
                if result[-1] != 201:
                    logging.error('Cannot create user {} : {}'.format(
                                  user_payload, result))
                    abort(500)
                logging.info('Create new user : {}'.format(user.email))
            return redirect('{}/#/?token={}'.format(
                current_app.config['FRONTEND_DOMAIN'], new_token), code=302)
    else:
        return authomatic.response


if __name__ == "__main__":
    import doctest
    doctest.testmod()
