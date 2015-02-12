#! /usr/bin/env python3

import redis
from flask import Flask
from flask.ext.pymongo import PyMongo

from . import settings
from .resources.utilisateurs import utilisateurs

from .xin.auth import TokenAuth, auth_factory
from .xin.tools import ObjectIdConverter


# def bootstrap():
#     config = Config(dirname(abspath(__file__)))
#     config.from_pyfile('settings.py')
#     resources = [
#         # utilisateurs,
#         fichiers,
#         taxons,
#         sites,
#         protocoles,
#         participations,
#         grille_stoc,
#         actualites]
#     config['DOMAIN'] = {r.name: r.domain for r in resources}
#     config['PROPAGATE_EXCEPTIONS'] = True


#     app = Eve(auth=TokenAuth, validator=Validator, redis=r, settings=config)
#     app.register_blueprint(auth_factory(settings.AUTHOMATIC.keys(),
#                                         mock_provider=settings.DEV_FAKE_AUTH))

#     for resource in resources:
#         app.register_blueprint(resource)
#     app.register_blueprint(utilisateurs.blueprint)
#     return app

from flask import Flask, jsonify
from werkzeug.exceptions import default_exceptions
from werkzeug.exceptions import HTTPException


def make_json_app(app):
    """
    Creates a JSON-oriented Flask app.

    All error responses that you don't specifically
    manage yourself will have application/json content
    type, and will contain JSON like this (just an example):

    { "message": "405: Method Not Allowed" }
    """
    def make_json_error(ex):
        # TODO : make this cleaner
        payload = {'_status': str(ex)}
        if hasattr(ex, 'description'):
            payload['_errors'] = ex.description
        response = jsonify(**payload)
        response.status_code = (ex.code if isinstance(ex, HTTPException) else 500)
        return response
    for code in default_exceptions.keys():
        app.error_handler_spec[None][code] = make_json_error


def init_app():
    app = Flask(__name__)
    app.config.from_pyfile('settings.py')
    app.data = PyMongo(app)
    app.redis = redis.StrictRedis(host=settings.REDIS_HOST,
                                  port=settings.REDIS_PORT, db=0)
    # Add objectid as url variable type
    app.url_map.converters['objectid'] = ObjectIdConverter
    app.register_blueprint(auth_factory(settings.AUTHOMATIC.keys(),
                                        mock_provider=settings.DEV_FAKE_AUTH))
    app.register_blueprint(utilisateurs)
    make_json_app(app)
    return app

app = init_app()

__all__ = ['app']
