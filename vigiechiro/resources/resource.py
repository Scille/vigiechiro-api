from flask import app, current_app
from flask import abort, url_for, Blueprint, redirect
from functools import wraps
from flask import request, Response, g, abort
from cerberus.errors import ERROR_BAD_TYPE


class ResourceException(Exception):
    pass


class Resource:

    def __init__(self):
        self.callbacks = []
        self.routes = []
        self.types = []
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
            event = getattr(
                app,
                '{}_{}'.format(
                    callback.__name__,
                    self.RESOURCE_NAME))
            event += callback
        if hasattr(self, 'blueprint'):
            app.register_blueprint(self.blueprint)
        for arg, kwargs in self.routes:
            self.blueprint
        for type_function in self.types:
            setattr(app.validator, type_function.__name__, type_function)

    def callback(self, f, name=None):
        """Decorator, register eve callback event based on function name"""
        if name:
            f.__name__ = name
        self.callbacks.append(f)
        return f

    def type(self, f, name=None):
        """Decorator, register cerberus type based on function name"""
        if name:
            f.__name__ = name
        else:
            f.__name__ = '_validate_' + f.__name__
        self.types.append(f)
        return f

    def register_type_enum(self, name, enum):
        """Create and register an enum validation function"""

        def check_type(self, field, value):
            if value not in enum:
                self._error(field, ERROR_BAD_TYPE % name)
        check_type.__name__ = '_validate_type_' + name
        self.types.append(check_type)

    def route(self, route_postfix, route_prefix=None, **kwargs):
        default_roles = kwargs.pop('allowed_roles', [])
        write_roles = kwargs.pop('allowed_write_roles', default_roles)
        read_roles = kwargs.pop('allowed_read_roles', default_roles)
        route_prefix = route_prefix or self.RESOURCE_NAME
        full_route = '/' + '/'.join([n for n in route_prefix.split('/') +
                                     route_postfix.split('/') if n])

        def fdec(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                resource = current_app.config['DOMAIN'][self.RESOURCE_NAME]
                roles = default_roles
                if request.method in ('GET', 'HEAD'):
                    roles += read_roles or (resource['allowed_read_roles'] +
                                            resource['allowed_roles'])
                elif request.method in ('PATCH', 'PUT', 'DELETE'):
                    roles += write_roles or (resource['allowed_write_roles'] +
                                             resource['allowed_roles'])
                elif request.method == 'OPTIONS':
                    send_response(resource, response)
                else:
                    abort(405)
                if current_app.auth:
                    if not current_app.auth.authorized(
                            roles,
                            None,
                            request.method):
                        return current_app.auth.authenticate()
                return f(*args, **kwargs)
            self.blueprint.add_url_rule(
                full_route,
                view_func=decorated,
                methods=kwargs.pop(
                    'methods',
                    []) +
                ['OPTIONS'],
                **kwargs)
            return decorated
        return fdec
