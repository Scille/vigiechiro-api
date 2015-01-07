#! /usr/bin/env python3

import random
import base64
import logging
import string
import types
from functools import wraps

from flask import Blueprint, redirect
from flask import app, current_app, abort, request
import eve.auth
import eve.render
from authomatic.extras.flask import FlaskAuthomatic

from vigiechiro import settings


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
    print(token)
    account = accounts.find_one({'tokens': token})
    if account and 'role' in account:
        # Keep request user account in local context, could be useful later
        current_app.g.request_user = account
        if allowed_roles:
            # Role are handled using least priviledge, thus a higher
            # priviledged role also include it lower roles.
            role = account['role']
            return next((True for r in current_app.config['ROLE_RULES'][role]
                         if r in allowed_roles), False)
        else:
            return True
    return False


def requires_auth(roles=None):
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


def auth_factory(services):
    """Generate flask blueprint of login endpoints
       :params services: list of services to generate endpoints

       >>> from flask import Flask
       >>> from vigiechiro.xin.auth import auth_factory
       >>> f = Flask('test')
       >>> blueprint = auth_factory(['github', 'google'])
       >>> f.register_blueprint(blueprint)
       >>> [url.rule for url in f.url_map.iter_rules()]
       ['/login/github', '/login/google', '/logout', '/static/<path:filename>']
    """
    authomatic = FlaskAuthomatic(config=settings.AUTHOMATIC,
                                 secret=settings.SECRET_KEY,
                                 debug=True)
    auth_blueprint = Blueprint('auth', __name__)

    def login_factory(service):
        return authomatic.login(service)(lambda: login(authomatic, service))
    for service in services:
        auth_blueprint.add_url_rule('/login/' + service, 'login_' + service,
                                    login_factory(service))

    @auth_blueprint.route('/logout', methods=['OPTIONS', 'POST'])
    @eve.auth.requires_auth('ressource')
    def logout():
        if request.authorization:
            token = request.authorization['username']
            users = auth_blueprint.data.driver.db['utilisateurs']
            if users.find_one({'tokens': token}):
                logging.info('Destroying token {}'.format(token))
                users.update({'tokens': token}, {'$pull': {'tokens': token}})
            else:
                abort(404)
        return eve.render.send_response(None, [])
    return auth_blueprint


def login(authomatic, provider_name):
    """Login/user register endpoint using authomatic for the heavy lifting"""
    if authomatic.result:
        if authomatic.result.error:
            return authomatic.result.error.message
        elif authomatic.result.user:
            authomatic.result.user.update()
            # Register the user
            token = ''.join(
                random.choice(
                    string.ascii_uppercase +
                    string.digits) for x in range(32))
            users_db = current_app.data.driver.db['utilisateurs']
            user = authomatic.result.user
            provider_id_name = provider_name + '_id'
            user_db = users_db.find_one({provider_id_name: user.id})
            if user_db:
                user_db_id = user_db['_id']
                users_db.update({provider_id_name: user.id},
                                {"$push": {'tokens': token}})
            else:
                user_db_id = users_db.insert({provider_id_name: user.id,
                                              'pseudo': user.name,
                                              'email': user.email,
                                              'tokens': [token],
                                              'role': 'Observateur'})
                logging.info('Create user {}'.format(user.email))
            logging.info(
                'Update user {} token: {}, Authorization: Basic {}'.format(
                    user.email,
                    token,
                    base64.encodebytes(
                        (token + ':').encode())))
            return redirect(
                '{}/#/?token={}&id={}&pseudo={}&email={}'.format(
                    current_app.config['FRONTEND_DOMAIN'],
                    token,
                    user_db_id,
                    user.name,
                    user.email),
                code=302)
    else:
        return authomatic.response


if __name__ == "__main__":
    import doctest
    doctest.testmod()
