from functools import wraps

from flask import Flask, Blueprint, current_app, abort
from datetime import datetime
from bson import ObjectId
import logging

from .cors import crossdomain
from .schema import Validator, Unserializer
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
        self.unserializer = Unserializer(schema)
        # Need to keep trace to provide consistent OPTIONS response in case
        # a route is registered more than one time with different methods
        self.methods_per_route = {}

    def route(self, route, *args, **kwargs):
        """Decorator, register flask route with cors support"""
        cors_kwargs = {}
        for field in ['origin', 'headers', 'max_age',
                      'attach_to_all', 'authomatics_options']:
            if field in kwargs:
                cors_kwargs[field] = kwargs.pop(field)
        if not route in self.methods_per_route:
            self.methods_per_route[route] = []
        if 'methods' in kwargs:
            methods = kwargs['methods']
            if isinstance(methods, str):
                self.methods_per_route.append(methods)
            elif isinstance(methods, list):
                self.methods_per_route[route] += methods
        cors_kwargs['get_methods'] = lambda: ', '.join(sorted(x.upper()
            for x in self.methods_per_route[route]))
        cors_decorator = crossdomain(**cors_kwargs)
        route_decorator = Blueprint.route(self, route, *args, **kwargs)

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
        result = self.validator.run(payload,
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

    def _atomic_update(self, lookup, payload, if_match=False, custom_merge=None):
        # Retrieve previous version of the document
        if isinstance(lookup, ObjectId):
            lookup = {'_id': lookup}
        if not isinstance(lookup, dict):
            raise ValueError("lookup must be ObjectId or dict")
        resource_db = current_app.data.db[self.name]
        document = resource_db.find_one(lookup)
        if not document:
            return (404, )
        old_etag = document.get('_etag', None)
        if not old_etag:
            logging.error('Errors in document {} : missing field _etag'.format(
                document['_id'], ))
            abort(500)
        # Check for race condition
        if if_match and old_etag != if_match:
            return (412, 'If-Match condition has failed')
        # Provide to the validator additional data needed for some validatations
        additional_context = {
            'resource': self,
            'old_document': document
        }
        # Validate payload against resource schema
        result = self.validator.run(payload, is_update=True,
                                    additional_context=additional_context)
        if result.errors:
            return (422, result.errors)
        # Merge payload to update existing document
        if custom_merge:
            document = custom_merge(document, payload)
        else:
            document.update(payload)
        # Complete the payload with metada
        document['_updated'] = datetime.utcnow().replace(microsecond=0)
        del document['_etag']
        document['_etag'] = build_etag(document)
        # Finally do the actual update in db using again the if_match
        # field in the lookup to prevent race condition
        result = resource_db.update(
            {'_id': document['_id'], '_etag': old_etag}, document)
        if not result['updatedExisting']:
            return (412, 'If-Match condition has failed')
        print('inserted document', document)
        return (200, document)

    def update(self, lookup, payload, if_match=False, auto_abort=True, custom_merge=None):
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
                result = self._atomic_update(lookup, payload.copy(),
                                             custom_merge=custom_merge)
                if result[0] != 412:
                    break
        else:
            # Else abort in case of race condition
            result = self._atomic_update(lookup, payload, if_match=if_match,
                                         custom_merge=custom_merge)
            if result[0] != 200:
                error(*result)
        return result[1]

    def find(self, *args, expend=[], **kwargs):
        # Provide to the validator additional data needed for some validatations
        additional_context = {
            'resource': self,
            'expend_data_relation': expend
        }
        docs = []
        cursor = current_app.data.db[self.name].find(*args, **kwargs)
        for document in cursor:
            result = self.unserializer.run(document)
            if result.errors:
                logging.error('Errors in document {} : {}'.format(
                    result.document['_id'], result.errors))
            docs.append(result.document)
        return docs, cursor.count(with_limit_and_skip=False)

    def remove(self, *args, **kwargs):
        return current_app.data.db[self.name].remove(*args, **kwargs)

    def find_one(self, *args, expend=[], **kwargs):
        document = current_app.data.db[self.name].find_one(*args, **kwargs)
        if document:
            # Provide to the validator additional data needed for some validatations
            additional_context = {
                'resource': self,
                'expend_data_relation': expend
            }
            result = self.unserializer.run(document)
            if result.errors:
                logging.error('Errors in document {} : {}'.format(
                    result.document['_id'], result.errors))
            document = result.document
        return document

    def get_resource(self, obj_id, auto_abort=True, projection=None):
        """Retrieve object from database with it ID and resource name"""
        return get_resource(self.name, obj_id, auto_abort=auto_abort,
                            projection=projection)
