#! /usr/bin/env python3

from eve import Eve
from os.path import dirname, abspath
import redis
from flask import Config

from . import settings, resources
from .resources import (utilisateurs, fichiers, taxons, sites, protocoles,
                        participations, grille_stoc, actualites)
from .xin import Validator
from .xin.auth import TokenAuth, auth_factory
from .scripts.hirefire import build_hirefire_blueprint

from hirefire.procs.celery import CeleryProc
from .scripts.celery import celery_app


def bootstrap():
    config = Config(dirname(abspath(__file__)))
    config.from_pyfile('settings.py')
    resources = [
        utilisateurs,
        fichiers,
        taxons,
        sites,
        protocoles,
        participations,
        grille_stoc,
        actualites]
    config['DOMAIN'] = {r.name: r.domain for r in resources}
    config['PROPAGATE_EXCEPTIONS'] = True

    r = redis.StrictRedis(host=settings.REDIS_HOST, port=settings.REDIS_PORT,
                          db=0)

    app = Eve(auth=TokenAuth, validator=Validator, redis=r, settings=config)
    app.register_blueprint(auth_factory(settings.AUTHOMATIC.keys(),
                                        mock_provider=settings.DEV_FAKE_AUTH))
    for resource in resources:
        app.register_blueprint(resource)

    # Init hirefire
    worker_proc = CeleryProc(name='worker', queues=['celery'], app=celery_app)
    app.register_blueprint(build_hirefire_blueprint(settings.HIREFIRE_TOKEN,
                                                    [worker_proc]))
    return app

app = bootstrap()

__all__ = ['app']
