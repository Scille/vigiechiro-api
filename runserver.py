#! /usr/bin/env python3

import logging
from vigiechiro import app, settings

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app.run(debug=True, port=settings.PORT)
