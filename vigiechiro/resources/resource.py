from flask import app, current_app
from flask import abort, url_for, Blueprint, redirect
from functools import wraps
from flask import request, Response, g, abort

class ResourceException(Exception): pass

class Resource:

    def __init__(self):
        self.callbacks = []
        self.routes = []
        missings = [mandatory for mandatory in ['DOMAIN', 'RESOURCE_NAME']
                    if mandatory not in dir(self)]
        if missings:
            raise ResourceException('{} : missing mandatory field(s) '
                                    ': {}'.format(self.__class__, missings))
        self.blueprint = Blueprint(self.RESOURCE_NAME, __name__)

    def register(self, app):
        """Register callback function (i.e. methods starting with 'on_') in
           the given eve app
        """
        for callback in self.callbacks:
            event = getattr(app, '{}_{}'.format(callback.__name__, self.RESOURCE_NAME))
            event += callback
        if hasattr(self, 'blueprint'):
            app.register_blueprint(self.blueprint)
        for arg, kwargs in self.routes:
            self.blueprint

    def callback(self, f):
        """Register eve callback event base on function name"""
        self.callbacks.append(f)
        return f

    def route(self, route_, **kwargs):
        default_roles = kwargs.pop('allowed_roles', [])
        write_roles = kwargs.pop('allowed_write_roles', default_roles)
        read_roles = kwargs.pop('allowed_read_roles', default_roles)
        def fdec(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                if request.method in ('GET', 'HEAD'):
                    roles = read_roles
                elif request.method in ('PATCH', 'PUT', 'DELETE'):
                    roles = write_roles
                elif request.method == 'OPTIONS':
                    send_response(resource, response)
                else:
                    abort(405)
                if current_app.auth:
                    if not current_app.auth.authorized(roles, None, request.method):
                        return current_app.auth.authenticate()
                return f(*args, **kwargs)
            self.blueprint.add_url_rule(route_, view_func=decorated,
                methods=kwargs.pop('methods', []) + ['OPTIONS'], **kwargs)
            return decorated
        return fdec
