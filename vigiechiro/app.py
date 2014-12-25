#! /usr/bin/env python3

from eve import Eve
from os.path import dirname, abspath
import redis
from vigiechiro import settings, resources
from vigiechiro.resources import utilisateurs, fichiers, taxons, sites, protocoles
from flask import Config
from .xin import Validator
from .xin.auth import TokenAuth, auth_factory


def bootstrap():
    config = Config(dirname(abspath(__file__)))
    config.from_pyfile('settings.py')
    resources = [utilisateurs, fichiers, taxons, sites, protocoles]
    config['DOMAIN'] = {
        resource.name: resource.domain for resource in resources}

    r = redis.StrictRedis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=0)

    app = Eve(auth=TokenAuth, validator=Validator, redis=r, settings=config)
    app.register_blueprint(auth_factory(['google', 'github']))
    for resource in resources:
        app.register_blueprint(resource)
    app.debug = True
    return app

app = bootstrap()
