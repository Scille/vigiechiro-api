#! /usr/bin/env python3

from eve import Eve
import logging

from vigiechiro import settings
from vigiechiro.auth import TokenAuth, auth_factory


app = Eve(auth=TokenAuth)
app.register_blueprint(auth_factory(['google', 'github']))

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app.run(debug=True, port=settings.PORT)
