from functools import wraps

from flask import Blueprint
from eve.flaskapp import Eve

from .cors import crossdomain


class EveBlueprint(Blueprint):

    """Extend the flask blueprint to provide eve's event and type support"""

    def __init__(self, *args, domain=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = domain
        self.events = []
        self.types = []

    def event(self, f, name=None):
        """Decorator, register eve event based on function name"""
        if name:
            f.__name__ = name
        self.events.append(f)
        return f

    def type(self, f, name=None):
        """Decorator, register cerberus type based on function name"""
        if name:
            f.__name__ = name
        self.events.append(f)
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
    if hasattr(blueprint, 'types'):
        for type_function in blueprint.types:
            setattr(self.validator, type_function.__name__, type_function)
    return wrapped(self, blueprint, *args, **kwargs)

Eve.register_blueprint = register_blueprint
