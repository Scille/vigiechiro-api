#! /usr/bin/env python3

import os
from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from  tornado.options import parse_command_line
from vigiechiro import app


def main():
    parse_command_line()
    port = int(os.environ.get("PORT", 8080))
    http_server = HTTPServer(WSGIContainer(app))
    http_server.listen(port)
    IOLoop.instance().start()

 
if __name__ == "__main__":
    main()
