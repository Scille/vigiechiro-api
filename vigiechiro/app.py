#! /usr/bin/env python3

import redis
import requests
import logging
from os.path import abspath, dirname
from flask import Flask, send_from_directory, make_response
from flask.ext.pymongo import PyMongo
from flask.ext.cache import Cache
from hirefire.procs.celery import CeleryProc

from . import settings
from . import resources

from .xin.auth import auth_factory
from .xin.tools import ObjectIdConverter
from .scripts.celery import celery_app
from .scripts.hirefire import build_hirefire_blueprint


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
    if not app.config.get('DEBUG', False):
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        app.logger.addHandler(stream_handler)
    # Configure static hosting of the front
    if app.config['FRONTEND_HOSTED']:
        cache = Cache(app, config={'CACHE_TYPE': 'simple'})
        app.root_path = abspath(dirname(__file__) + '/..')
        redirect_url = app.config['FRONTEND_HOSTED_REDIRECT_URL']

        @app.route('/')
        @app.route('/<path:path>')
        @cache.cached(timeout=600)
        def host_front(path='index.html'):
            if redirect_url:
                target = '{}/{}'.format(redirect_url, path)
                r = requests.get(target)
                if r.status_code != 200:
                    app.logger.error('cannot fetch {}, error {} : {}'.format(
                        target, r.status_code, r.data))
                response = make_response(r.content, r.status_code)
                for key, value in r.headers.items():
                    response.headers[key] = value
                return response
            return send_from_directory('static', path)
    app.data = PyMongo(app)
    app.redis = redis.StrictRedis(host=settings.REDIS_HOST,
                                  port=settings.REDIS_PORT, db=0)
    # Add objectid as url variable type
    app.url_map.converters['objectid'] = ObjectIdConverter
    url_prefix = app.config['BACKEND_URL_PREFIX']
    app.register_blueprint(auth_factory(settings.AUTHOMATIC.keys(),
                                        mock_provider=settings.DEV_FAKE_AUTH),
                           url_prefix=url_prefix)
    app.register_blueprint(resources.utilisateurs, url_prefix=url_prefix)
    app.register_blueprint(resources.taxons, url_prefix=url_prefix)
    app.register_blueprint(resources.protocoles, url_prefix=url_prefix)
    app.register_blueprint(resources.fichiers, url_prefix=url_prefix)
    app.register_blueprint(resources.grille_stoc, url_prefix=url_prefix)
    app.register_blueprint(resources.actualites, url_prefix=url_prefix)
    app.register_blueprint(resources.sites, url_prefix=url_prefix)
    app.register_blueprint(resources.participations, url_prefix=url_prefix)
    app.register_blueprint(resources.donnees, url_prefix=url_prefix)
    make_json_app(app)
    # Init hirefire
    worker_proc = CeleryProc(name='worker', queues=['celery'], app=celery_app)
    app.register_blueprint(build_hirefire_blueprint(settings.HIREFIRE_TOKEN,
                                                    [worker_proc]))
    return app


app = init_app()

__all__ = ['app']
