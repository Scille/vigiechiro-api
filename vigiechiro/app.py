#! /usr/bin/env python3

import redis
from flask import Flask
from flask.ext.pymongo import PyMongo

from . import settings
from . import resources

from .xin.auth import auth_factory
from .xin.tools import ObjectIdConverter


def make_json_app(app):
    from flask import Flask, jsonify
    from werkzeug.exceptions import default_exceptions
    from werkzeug.exceptions import HTTPException
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
    app.register_blueprint(resources.utilisateurs)
    app.register_blueprint(resources.taxons)
    app.register_blueprint(resources.protocoles)
    app.register_blueprint(resources.fichiers)
    app.register_blueprint(resources.grille_stoc)
    app.register_blueprint(resources.actualites)
    app.register_blueprint(resources.sites)
    app.register_blueprint(resources.participations)
    app.register_blueprint(resources.donnees)
    make_json_app(app)
    return app


app = init_app()

__all__ = ['app']
