#! /usr/bin/env python3

from vigiechiro import app, settings

if __name__ == '__main__':
    app.run(debug=True, port=settings.PORT)
