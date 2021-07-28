from functools import wraps

from flask import Flask, Blueprint, current_app, abort, make_response
from datetime import datetime
from bson import ObjectId
import logging
from uuid import uuid4

from .cors import crossdomain
from .schema import Validator, Unserializer
from .tools import build_etag, jsonify
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
            @route_decorator
            @cors_decorator
            @wraps(f)
            def wrapper(*args, **kwargs):
                result = f(*args, **kwargs)
                # if result contains a dict, assume the response is json
                if isinstance(result, dict):
                    payload = result
                    return jsonify(**result)
                elif isinstance(result, tuple) and isinstance(result[0], dict):
                    response = jsonify(**result[0])
                    if len(result) >= 2:
                        response.status_code = result[1]
                    if len(result) == 3:
                        for field, value in result[3]:
                            response.headers[field] = value

                    return response
                else:
                    return result
        return decorator

    def insert(self, payload, auto_abort=True, additional_context=None):
        """Insert in database a new document of the resource"""
        # Provide to the validator additional data needed for some validatations
        additional_context = additional_context or {}
        additional_context['resource'] = self
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
        payload['_etag'] = uuid4().hex
        # Finally do the actual insert in db
        insert_result = current_app.data.db[self.name].insert_one(payload)
        payload['_id'] = insert_result.inserted_id
        return payload

    def _atomic_update(self, lookup, payload, mongo_update=None,
                       if_match=False, additional_context=None):
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
            logging.error('Errors in document {} {} : missing field _etag'.format(
                self.name, document['_id']))
            abort(500)
        # Check for race condition
        if if_match and old_etag != if_match:
            return (412, 'If-Match condition has failed')
        # Provide to the validator additional data needed for some validatations
        additional_context = additional_context or {}
        additional_context['resource'] = self
        additional_context['old_document'] = document
        # Validate payload against resource schema
        result = self.validator.run(payload, is_update=True,
                                    additional_context=additional_context)
        if result.errors:
            return (422, result.errors)
        # Fill metada and update the resource in db
        if not mongo_update:
            mongo_update = {'$set': payload}
        if '$set' not in mongo_update:
            mongo_update['$set'] = {}
        mongo_update['$set']['_updated'] = datetime.utcnow().replace(microsecond=0)
        mongo_update['$set']['_etag'] = uuid4().hex
        # Finally do the actual update in db using again the _etag
        # field in the lookup to prevent race condition
        lookup = lookup.copy()
        if '_etag' not in lookup:
            lookup['_etag'] = old_etag
        new_document = resource_db.find_and_modify(
            query=lookup,
            update=mongo_update, new=True)
        if not new_document:
            return (412, 'If-Match condition has failed')
        return (200, new_document)

    def insert_or_replace(self, lookup, payload, auto_abort=True):
        def error(code, msg=None):
            if auto_abort:
                abort(code, msg)
            else:
                raise DocumentException((code, msg))
        mongo_update = payload.copy()
        mongo_update['_created'] = mongo_update['_updated'] = datetime.utcnow().replace(microsecond=0)
        mongo_update['_etag'] = uuid4().hex
        # Retrieve previous version of the document
        if isinstance(lookup, ObjectId):
            lookup = {'_id': lookup}
        if not isinstance(lookup, dict):
            raise ValueError("lookup must be ObjectId or dict")
        resource_db = current_app.data.db[self.name]
        new_document = resource_db.find_and_modify(
            query=lookup,
            update=mongo_update, new=True, upsert=True)
        if not new_document:
            return error(412, 'If-Match condition has failed')
        return self._unserialize_document(new_document).document

    def update(self, lookup, payload, mongo_update=None, if_match=False,
               auto_abort=True, additional_context=None):
        """
            Update in database a document of the resource
            :param payload: data dict to run the validator against
            :param mongo_update: mongodb commands (i.g. "$set", "$inc" etc...),
                                 to use to update in database instead of using
                                 {'$set': payload}
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
        if not if_match:
            # No if_match, in case of race condition, repeatedly try the update
            while True:
                result = self._atomic_update(lookup, payload.copy(),
                                             mongo_update=mongo_update,
                                             additional_context=additional_context)
                if result[0] != 412:
                    break
        else:
            # Else abort in case of race condition
            result = self._atomic_update(lookup, payload, if_match=if_match,
                                         mongo_update=mongo_update)
        if result[0] != 200:
            error(*result)
        # Unserialize and return our new document
        return self._unserialize_document(result[1]).document

    def find(self, *args, additional_context=None, **kwargs):
        cursor = current_app.data.db[self.name].find(*args, **kwargs)

        _lazy_fetch_and_unserialize = (
            self._unserialize_document(
                document,
                additional_context=additional_context
            ).document
            for document in cursor
        )

        return _lazy_fetch_and_unserialize, cursor.count(with_limit_and_skip=False)

    def remove(self, *args, **kwargs):
        return current_app.data.db[self.name].delete_one(*args, **kwargs)

    def find_one(self, *args, additional_context=None, auto_abort=True, **kwargs):
        document = current_app.data.db[self.name].find_one(*args, **kwargs)
        if document:
            # Provide to the validator additional data needed for some validatations
            result = self._unserialize_document(document,
                additional_context=additional_context)
            document = result.document
        elif auto_abort:
            abort(404)
        return document

    def _unserialize_document(self, document, additional_context=None):
        # Provide to the validator additional data needed for some validatations
        additional_context = additional_context or {}
        additional_context['resource'] = self
        result = self.unserializer.run(document,
                                       additional_context=additional_context)
        if result.errors:
            logging.error('Errors in document {} {} : {}'.format(
                self.name, result.document['_id'], result.errors))
        return result

    def get_resource(self, obj_id, auto_abort=True, projection=None):
        """Retrieve object from database with it ID and resource name"""
        return get_resource(self.name, obj_id, auto_abort=auto_abort,
                            projection=projection)

    def build_db_indexes(clean=False):
        """Initialize the database with the given indexes"""
        pass
