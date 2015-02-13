from functools import wraps

from flask import Flask, Blueprint, current_app, abort
from datetime import datetime

from .cors import crossdomain
from .schema import Validator
from .tools import build_etag
from .snippets import get_resource


RESERVED_FIELD = {'_id', '_created', '_updated', '_etag'}

class DocumentException(Exception): pass
class SchemaException(Exception): pass

class Resource(Blueprint):

    """
        A resource is a set of flask routes (stored into a Blueprint) working
        on a mongodb collection.

        :param name: name of the resource, will determine the mongodb
                     collection to work on
        :param schema: schema to use to validate the resources
    """

    def __init__(self, name, *args, schema=None, **kwargs):
        super().__init__(name, *args, **kwargs)
        self.name = name
        self.schema = schema
        # Add default fields to the schema
        if RESERVED_FIELD - set(schema.keys()) != RESERVED_FIELD:
            raise SchemaException('Schema should not contain fields {}'.format(RESERVED_FIELD))
        schema['_id'] = {'type': 'string', 'readonly': True}
        schema['_created'] = {'type': 'string', 'readonly': True}
        schema['_updated'] = {'type': 'string', 'readonly': True}
        schema['_etag'] = {'type': 'string', 'readonly': True}
        self.validator = Validator(schema)

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

    def insert(self, payload, auto_abort=True):
        """Insert in database a new document of the resource"""
        # Provide to the validator additional data needed for some validatations
        additional_context = {
            'resource': self,
        }
        # Validate payload against resource schema
        result = self.validator.validate(payload,
                                         additional_context=additional_context)
        if result.errors:
            if auto_abort:
                abort(422, result.errors)
            else:
                raise DocumentException(result.errors)
        # Complete the payload with metada
        payload['_created'] = payload['_updated'] = datetime.utcnow().replace(microsecond=0)
        payload['_etag'] = build_etag(payload)
        # Finally do the actual insert in db
        payload['_id'] = current_app.data.db[self.name].insert(payload)
        return payload

    def update(self, id, payload, if_match, auto_abort=True):
        """Update in database a new document of the resource"""
        # Retreive and check payload
        if not payload:
            if auto_abort:
                abort(422, 'Bad payload')
            else:
                raise DocumentException('Bad payload')
        # Retrieve previous version of the document
        old_document = current_app.data.db[self.name].find_one({'_id': id})
        if not old_document:
            abort(404)
        # Check If-Match conidition
        if old_document.get('_etag', '') != if_match:
            abort(412, 'If-Match condition has failed')
        # Provide to the validator additional data needed for some validatations
        additional_context = {
            'resource': self,
            'old_document': old_document
        }
        # Validate payload against resource schema
        result = self.validator.validate(payload, is_update=True,
                                         additional_context=additional_context)
        if result.errors:
            if auto_abort:
                abort(422, result.errors)
            else:
                raise DocumentException(result.errors)
        # Complete the payload with metada
        payload['_updated'] = datetime.utcnow().replace(microsecond=0)
        payload['_etag'] = build_etag(payload)
        # Finally do the actual update in db using again the if_match
        # field in the lookup to prevent race condition
        result = current_app.data.db[self.name].update(
            {'_id': id, '_etag': if_match}, {'$set': payload})
        if not result['updatedExisting']:
            if auto_abort:
                abort(412, 'If-Match condition has failed')
            else:
                raise DocumentException('If-Match condition has failed')
        return payload

    def find(self, *args, **kwargs):
        return current_app.data.db[self.name].find(*args, **kwargs)

    def find_one(self, *args, **kwargs):
        return current_app.data.db[self.name].find_one(*args, **kwargs)

    def get_resource(self, obj_id, auto_abort=True, projection=None):
        """Retrieve object from database with it ID and resource name"""
        return get_resource(self.name, obj_id, auto_abort, projection)
