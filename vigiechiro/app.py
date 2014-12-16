#! /usr/bin/env python3

from eve import Eve
from os.path import dirname, abspath
import logging
import redis

from vigiechiro import settings
from vigiechiro.validator import Validator
from vigiechiro.auth import TokenAuth, auth_factory

r = redis.StrictRedis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)
app = Eve(auth=TokenAuth, validator=Validator, redis=r,
          settings=dirname(abspath(__file__)) + '/settings.py')
app.register_blueprint(auth_factory(['google', 'github']))

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app.run(debug=True, port=settings.PORT)
