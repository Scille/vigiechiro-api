from functools import wraps

from flask import Blueprint
from eve.flaskapp import Eve

from .cors import crossdomain


class EveBlueprint(Blueprint):

    """
        Extend the flask blueprint to provide eve's event and type support

        :param auto_prefix: automatically add prefix base on blueprint
            name to url and callbacks

            >>> from vigiechiro.xin import EveBlueprint
            >>> bp = EveBlueprint('myresource', 'vigiechiro.xin', auto_prefix=True)
            >>> @bp.event
            ... def on_POST(): pass
            ...
            >>> @bp.validate
            ... def type_custom(): pass
            ...
            >>> [f.__name__ for f in bp.events + bp.validates]
            ['on_POST_myresource', '_validate_type_custom']

        :param domain: Eve domain dict for the given resource :ref: eve.Eve
    """

    def __init__(
            self,
            name,
            import_name,
            *args,
            auto_prefix=False,
            domain=None,
            **kwargs):
        if auto_prefix:
            if 'url_prefix' not in kwargs:
                kwargs['url_prefix'] = '/' + name
            self.event_prefix = '_' + name
            self.validate_prefix = '_validate_'
        else:
            self.event_prefix = None
        super().__init__(name, import_name, *args, **kwargs)
        self.domain = domain
        self.events = []
        self.validates = []

    def event(self, f, name=None):
        """Decorator, register eve event based on function name"""
        if name:
            f.__name__ = name
        elif self.event_prefix:
            f.__name__ = f.__name__ + self.event_prefix
        self.events.append(f)
        return f

    def validate(self, f, name=None):
        """Decorator, register cerberus validate based on function name"""
        if name:
            f.__name__ = name
        elif self.validate_prefix:
            f.__name__ = self.validate_prefix + f.__name__
        self.validates.append(f)
        return f

    def route(self, *args, **kwargs):
        """Decorator, register flask route with cors support"""
        cors_kwargs = {}
        if 'methods' in kwargs:
            cors_kwargs['methods'] = kwargs['methods']
        for field in ['origin', 'headers', 'max_age',
                      'attach_to_all', 'authomatics_options']:
            if field in kwargs:
                cors_kwargs[field] = kwargs.pop(field)
        cors_decorator = crossdomain(**cors_kwargs)
        route_decorator = Blueprint.route(self, *args, **kwargs)

        def decorator(f):
            return route_decorator(cors_decorator(f))
        return decorator

# It's monkey patching time !
wrapped = Eve.register_blueprint


@wraps(wrapped)
def register_blueprint(self, blueprint, *args, **kwargs):
    """Load the blueprint in the eve app :
        - register events
        - regist custom types
        - finally connect the flask blueprint
    """
    if hasattr(blueprint, 'events'):
        for event in blueprint.events:
            slot = getattr(self, event.__name__)
            slot += event
    if hasattr(blueprint, 'validates'):
        for validate in blueprint.validates:
            setattr(self.validator, validate.__name__, validate)
    return wrapped(self, blueprint, *args, **kwargs)

Eve.register_blueprint = register_blueprint

__all__ = ['EveBlueprint', 'register_blueprint']
