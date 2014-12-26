from functools import wraps

from flask import Blueprint
from eve.flaskapp import Eve

from .cors import crossdomain


class EveBlueprint(Blueprint):

    """
    Extend the flask blueprint to provide eve's event and type support
    :param auto_prefix: automatically add prefix base on blueprint name to url and callbacks
    :param domain: Eve domain dict for the given resource
    """

    def __init__(self, name, *args, auto_prefix=False, domain=None, **kwargs):
        if auto_prefix:
            if 'url_prefix' not in kwargs:
                kwargs['url_prefix'] = '/' + name
            self.event_prefix = '_' + name
            self.validate_prefix = '_validate_'
        else:
            self.event_prefix = None
        super().__init__(name, *args, **kwargs)
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
