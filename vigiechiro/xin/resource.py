from functools import wraps

from flask import Flask, Blueprint, current_app, abort
from datetime import datetime
from bson import ObjectId

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

    def _atomic_update(self, obj_id, payload, if_match=False):
        # Retrieve previous version of the document
        if not isinstance(obj_id, ObjectId):
            raise ValueError("obj_id must be ObjectId")
        document = self.find_one({'_id': obj_id})
        if not document:
            return (404, )
        old_etag = document['_etag']
        # Check for race condition
        if if_match and old_etag != if_match:
            return (412, 'If-Match condition has failed')
        # Provide to the validator additional data needed for some validatations
        additional_context = {
            'resource': self,
            'old_document': document
        }
        # Validate payload against resource schema
        result = self.validator.validate(payload, is_update=True,
                                         additional_context=additional_context)
        if result.errors:
            return (422, result.errors)
        # Merge payload to update existing document
        document.update(payload)
        # Complete the payload with metada
        document['_updated'] = datetime.utcnow().replace(microsecond=0)
        del document['_etag']
        document['_etag'] = build_etag(document)
        # Finally do the actual update in db using again the if_match
        # field in the lookup to prevent race condition
        result = current_app.data.db[self.name].update(
            {'_id': obj_id, '_etag': old_etag}, document)
        if not result['updatedExisting']:
            return (412, 'If-Match condition has failed')
        return (200, document)

    def update(self, obj_id, payload, if_match=False, auto_abort=True):
        """
            Update in database a document of the resource
            :param if_match: race condition politic, if if_match is False the
                             update will be repeatedly tried until accepted,
                             if if_match is an etag, the update will be rejected
                             if it differs from the document's etag
        """
        def error(code, msg=None):
            if auto_abort:
                abort(code, msg)
            else:
                raise DocumentException((code, msg))
        # Retrieve and check payload
        if not payload:
            error(422, 'bad payload')
        if not if_match:
            # No if_match, in case of race condition, repeatedly try the update
            while True:
                result = self._atomic_update(obj_id, payload.copy())
                if result[0] != 412:
                    break
        else:
            # Else abort in case of race condition
            result = self._atomic_update(obj_id, payload, if_match=if_match)
            if result[0] != 200:
                error(*result)
        return result[1]

    def find(self, *args, **kwargs):
        return current_app.data.db[self.name].find(*args, **kwargs)

    def remove(self, *args, **kwargs):
        return current_app.data.db[self.name].remove(*args, **kwargs)

    def find_one(self, *args, **kwargs):
        return current_app.data.db[self.name].find_one(*args, **kwargs)

    def get_resource(self, obj_id, auto_abort=True, projection=None):
        """Retrieve object from database with it ID and resource name"""
        return get_resource(self.name, obj_id, auto_abort, projection)
