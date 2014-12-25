#! /usr/bin/env python3

from eve import Eve
from os.path import dirname, abspath
import redis
from vigiechiro import settings, resources
from vigiechiro.resources import fichiers, utilisateurs, taxons, sites
from flask import Config
from .xin import Validator
from .xin.auth import TokenAuth, auth_factory


def bootstrap():
    config = Config(dirname(abspath(__file__)))
    config.from_pyfile('settings.py')
    config['DOMAIN'] = resources.generate_domain()
    config['DOMAIN'][fichiers.name] = fichiers.domain
    config['DOMAIN'][utilisateurs.name] = utilisateurs.domain
    config['DOMAIN'][taxons.name] = taxons.domain
    config['DOMAIN'][sites.name] = sites.domain

    r = redis.StrictRedis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=0)

    app = Eve(auth=TokenAuth, validator=Validator, redis=r, settings=config)
    app.register_blueprint(auth_factory(['google', 'github']))
    app.register_blueprint(fichiers)
    app.register_blueprint(utilisateurs)
    app.register_blueprint(taxons)
    app.register_blueprint(sites)
    app.debug = True
    resources.register_app(app)
    return app

app = bootstrap()
