"""
    CORS support
    ~~~~~~~~~~~~

    see: http://flask.pocoo.org/snippets/56/
"""

from datetime import timedelta
from flask import make_response, request, current_app, abort
from functools import update_wrapper, wraps

from .. import settings


def add_cors_headers_factory(origin=None, methods=None, headers=None, max_age=21600, get_methods=None):
    origin = origin or settings.X_DOMAINS
    headers = headers or settings.X_HEADERS
    if headers is not None and not isinstance(headers, str):
        headers = ', '.join(x.upper() for x in headers)
    if not isinstance(origin, str):
        origin = ', '.join(origin)
    if isinstance(max_age, timedelta):
        max_age = max_age.total_seconds()
    if not get_methods:
        if isinstance(methods, list):
            methods = ', '.join(sorted(x.upper() for x in methods))
        def get_methods():
            if methods != None:
                return methods
            options_resp = current_app.make_default_options_response()
            return options_resp.headers.get('allow')

    def add_cors_headers(resp):
        h = resp.headers
        h['Access-Control-Allow-Credentials'] = 'true'
        h['Access-Control-Allow-Origin'] = origin
        h['Access-Control-Allow-Methods'] = get_methods() or request.method
        h['Access-Control-Max-Age'] = str(max_age)
        if headers is not None:
            h['Access-Control-Allow-Headers'] = headers
        return resp

    return add_cors_headers


def crossdomain(origin=None, methods=None, headers=None, max_age=21600,
                attach_to_all=True, automatic_options=True, get_methods=None):
    """A decorator to provide cors support for a flask route"""
    add_cors_headers = add_cors_headers_factory(
        origin=origin, methods=methods, headers=headers,
        max_age=max_age, get_methods=get_methods)

    def decorator(f):
        def wrapped_function(*args, **kwargs):
            if automatic_options and request.method == 'OPTIONS':
                resp = current_app.make_default_options_response()
            else:
                resp = make_response(f(*args, **kwargs))
            return add_cors_headers(resp)
        f.required_methods = ['OPTIONS']
        f.provide_automatic_options = False
        return update_wrapper(wrapped_function, f)
    return decorator
