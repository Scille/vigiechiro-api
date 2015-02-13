"""
    Validator module
    ~~~~~~~~~~~~~~~~

    Rewrite of Cerberus schema validator
"""

import re
from flask import request, g, current_app
from cerberus.errors import ERROR_BAD_TYPE, ERROR_READONLY_FIELD
from bson import ObjectId
from datetime import datetime
from collections import Mapping, Sequence

from .tools import str_to_date, parse_id


def relation(resource, embeddable=True, field='_id', **kwargs):
    """Data model template for a resource relation"""
    kwargs.update({'type': 'objectid',
                   'data_relation': {
                       'resource': resource,
                       'field': field,
                       'embeddable': embeddable
                   }
                   })
    return kwargs


def choice(choices, **kwargs):
    """Data model template for a regex choice"""
    kwargs.update({'type': 'string',
                   'regex': r'^({})$'.format('|'.join(choices))})
    return kwargs


class ValidatorContext:
    """Validation result object"""

    def __init__(self, schema, document, is_update=False, additional_context=None):
        self.schema = schema
        self.document = document
        self.is_update = is_update
        self.additional_context = additional_context or {}
        self._stack = []
        self.errors = {}
        self.field = ''
        self.value = document
        self.is_valid = True

    def push(self, schema, field, value):
        self._stack.append((self.schema, self.field, self.value))
        self.schema = schema
        self.field = field
        self.value = value

    def pop(self):
        poped = (self.schema, self.field, self.value)
        self.schema, self.field, self.value = self._stack.pop()
        return poped

    def get_current_path(self):
        path = ''
        fields = [f for _, f, _ in self._stack] + [self.field]
        for field in fields:
            if not field:
                continue
            elif isinstance(field, int):
                path += '[{}]'.format(field)
            else:
                path += '.{}'.format(field) if path else field
        return path

    def add_error(self, msg):
        self.is_valid = False
        path = self.get_current_path()
        if path not in self.errors:
            self.errors[path] = msg
        elif isinstance(self.errors[path], list):
            self.errors[path].append(msg)
        else:
            self.errors[path] = [self.errors[path], msg]


class ValidatorSchemaException(Exception): pass
class GenericValidator:

    ERROR_SCHEMA_MISSING = "validation schema missing"
    ERROR_SCHEMA_FORMAT = "'%s' is not a schema, must be a dict"
    ERROR_DOCUMENT_MISSING = "document is missing"
    ERROR_DOCUMENT_FORMAT = "'%s' is not a document, must be a dict"
    ERROR_UNKNOWN_RULE = "unknown rule '%s' for field '%s'"
    ERROR_DEFINITION_FORMAT = "schema definition for field '%s' must be a dict"
    ERROR_UNKNOWN_FIELD = "unknown field"
    ERROR_REQUIRED_FIELD = "required field"
    ERROR_UNKNOWN_TYPE = "unrecognized data-type '%s'"
    ERROR_BAD_TYPE = "must be of %s type"
    ERROR_MIN_LENGTH = "min length is %d"
    ERROR_MAX_LENGTH = "max length is %d"
    ERROR_UNALLOWED_VALUES = "unallowed values %s"
    ERROR_UNALLOWED_VALUE = "unallowed value %s"
    ERROR_ITEMS_LIST = "length of list should be %d"
    ERROR_MAX_VALUE = "max value is %d"
    ERROR_MIN_VALUE = "min value is %d"
    ERROR_READONLY_FIELD = "field is read-only"
    ERROR_EMPTY_NOT_ALLOWED = "empty values not allowed"
    ERROR_NOT_NULLABLE = "null value not allowed"
    ERROR_REGEX = "value does not match regex '%s'"
    ERROR_DEPENDENCIES_FIELD = "field '%s' is required"
    ERROR_DEPENDENCIES_FIELD_VALUE = "field '%s' is required with values: %s"

    def __init__(self, schema):
        self.schema = schema
        # Dynamic init of generic types
        self._validate_type_factory(int, 'integer')
        self._validate_type_factory(str, 'string')
        self._validate_type_factory(float, 'float')
        self._validate_type_factory(bool, 'boolean')
        self._validate_type_factory(float, 'float')

    def type(self, validate_function, serializer=None, name=None):
        """Decorator, register a validate type based on function name"""
        if not name:
            name = validate_function.__name__
        setattr(self, '_validate_type_' + name, validate_function)
        setattr(self, '_validate_serializer_type_' + name, serializer)

    def attribute(self, validate_function, name=None):
        """Decorator, register a validate attribute based on function name"""
        if not name:
            name = validate_function.__name__
        setattr(self, '_validate_attribute_' + name, validate_function)

    def validate(self, document, is_update=False, additional_context=None):
        context = ValidatorContext({'type': 'dict', 'schema': self.schema},
                                   document, is_update=is_update,
                                   additional_context=additional_context)
        self._validate_schema(context)
        return context

    def _validate_type_factory(self, type, type_name):
        def validate(context):
            if not isinstance(context.value, type):
                context.add_error(self.ERROR_BAD_TYPE % type_name)
        setattr(self, '_validate_type_' + type_name, validate)

    def _validate_attribute_readonly(self, context):
        if context.schema['read_only']:
            context.add_error(self.ERROR_READONLY_FIELD)

    def _validate_attribute_regex(self, context):
        regex = context.schema['regex']
        pattern = re.compile(regex)
        if not pattern.match(context.value):
            context.add_error(self.ERROR_REGEX % regex)

    def _validate_type_datetime(self, context):
        # If value is not a datetime object, try to unserialize it
        if isinstance(context.value, str):
            # If the unserialized succeed, update the context stack
            unserialized = str_to_date(context.value)
            if unserialized:
                schema, field, _ = context.pop()
                context.value[field] = unserialized
                context.push(schema, field, unserialized)
        if not isinstance(context.value, datetime):
            context.add_error(self.ERROR_BAD_TYPE % "datetime")

    def _validate_type_objectid(self, context):
        # If value is not a ObjectId object, try to unserialize it
        if isinstance(context.value, str):
            # If the unserialized succeed, update the context stack
            unserialized = parse_id(context.value)
            if unserialized:
                schema, field, _ = context.pop()
                context.value[field] = unserialized
                context.push(schema, field, unserialized)
        if not isinstance(context.value, ObjectId):
            context.add_error(self.ERROR_BAD_TYPE % 'ObjectId')

    def _validate_type_url(self, context):
        """Basic url regex filter"""
        if not re.match(r"^https?://", context.value):
            context.add_error(self.ERROR_BAD_TYPE % 'url')

    def _validate_attribute_maxlength(self, context):
        max_length = context.schema['maxlength']
        if isinstance(context.value, Sequence):
            if len(context.value) > max_length:
                context.add_error(self.ERROR_MAX_LENGTH % max_length)

    def _validate_attribute_minlength(self, context):
        min_length = context.schema['minlength']
        if isinstance(context.value, Sequence):
            if len(context.value) < min_length:
                context.add_error(self.ERROR_MIN_LENGTH % min_length)

    def _validate_attribute_max(self, context):
        max = context.schema['max']
        if isinstance(context.value, (_int_types, float)):
            if context.value > max_value:
                context.add_error(self.ERROR_MAX_VALUE % max_value)

    def _validate_attribute_min(self, context):
        min = context.schema['min']
        if isinstance(context.value, (_int_types, float)):
            if context.value < min_value:
                context.add_error(self.ERROR_MIN_VALUE % min_value)

    def _validate_attribute_allowed(self, context):
        allowed_values = context.schema['allowed']
        if isinstance(context.value, str):
            if context.value not in allowed_values:
                context.add_error(self.ERROR_UNALLOWED_VALUE % context.value)
        elif isinstance(context.value, Sequence):
            disallowed = set(context.value) - set(allowed_values)
            if disallowed:
                context.add_error(self.ERROR_UNALLOWED_VALUES % list(disallowed))
        elif isinstance(context.value, int):
            if context.value not in allowed_values:
                context.add_error(self.ERROR_UNALLOWED_VALUE % context.value)

    def _validate_attribute_empty(self, context):
        empty = context.schema['empty']
        if isinstance(context.value, str) and len(context.value) == 0 and not empty:
            context.add_error(self.ERROR_EMPTY_NOT_ALLOWED)

    def _validate_attribute_schema(self, context):
        # Stub, schema is handled in `_validate_type_list` and
        # `_validate_type_dict`
        pass

    def _validate_attribute_keyschema(self, context):
        # Stub, schema is handled in `_validate_type_dict`
        pass

    def _validate_schema(self, context):
       for attribute in context.schema.keys():
            validate_attribute = getattr(self, "_validate_attribute_" + attribute, None)
            if not validate_attribute:
                raise ValidatorSchemaException('{} : unknown attribute `{}`'.format(
                    context.get_current_path(), attribute))
            validate_attribute(context)

    def _validate_attribute_type(self, context):
        type_name = context.schema['type']
        # Retrieve the validate function among object's methods
        validate_type = getattr(self, "_validate_type_" + type_name, None)
        if not validate_type:
            raise ValidatorSchemaException('{} : unknown type `{}`'.format(
                context.get_current_path(), type_name))
        validate_type(context)

    def _validate_attribute_required(self, context):
        # Stub, required is handled in `_validate_type_dict`
        pass

    def _validate_type_list(self, context):
        if not isinstance(context.value, list):
            context.add_error(self.ERROR_BAD_TYPE % 'list')
            return
        list_schema = context.schema.get('schema', None)
        if not list_schema:
            raise ValidatorSchemaException('List must have a `schema` attribute')

        for i, elem in enumerate(context.value):
            context.push(list_schema, i, elem)
            self._validate_schema(context)
            context.pop()

    def _validate_type_dict(self, context):
        if not isinstance(context.value, dict):
            context.add_error(self.ERROR_BAD_TYPE % 'dict')
            return
        # Check for unexpected fields
        dict_schema = context.schema.get('schema', None)
        dict_keyschema = context.schema.get('keyschema', None)
        if not dict_schema and not dict_keyschema:
            raise ValidatorSchemaException('Dict must have a `schema` or a `keyschema` attribute')
        if dict_schema and dict_keyschema:
            raise ValidatorSchemaException('Dict cannot have both `schema` or `keyschema` attributes')
        if dict_schema:
            dict_schema_keys = set(dict_schema.keys())
            value_keys = set(context.value.keys())
            unexpected_fiels = value_keys - dict_schema_keys
            for field in unexpected_fiels:
                value = context.value.pop(field)
                context.push(None, field, value)
                context.add_error(self.ERROR_UNKNOWN_FIELD)
                context.pop()
            # Check for missing required fields
            if not context.is_update:
                missing_fields = dict_schema_keys - value_keys
                for field in missing_fields:
                    if dict_schema[field].get('required', False):
                        context.push(dict_schema[field], field, None)
                        context.add_error(self.ERROR_REQUIRED_FIELD)
                        context.pop()
            # Now recursively validate each field
            for field, value in context.value.items():
                context.push(dict_schema[field], field, value)
                self._validate_schema(context)
                context.pop()
        if dict_keyschema:
            # Just recursively validate each sub item
            for field, value in context.value.items():
                context.push(dict_keyschema, field, value)
                self._validate_schema(context)
                context.pop()


class Validator(GenericValidator):

    ERROR_UNIQUE_FIELD = "value '%s' is not unique"

    def _validate_attribute_postonly(self, context):
        """Field can be altered by non-admin during POST only"""
        post_only = context.schema['postonly']
        if g.request_user['role'] == 'Administrateur':
            return
        if post_only and request.method != 'POST':
            context.add_error(self.ERROR_READONLY_FIELD)

    def _validate_attribute_writerights(self, context):
        """Limit write rights to write_roles"""
        write_roles = context.schema['writerights']
        if isinstance(write_roles, str):
            write_roles = [write_roles]
        if g.request_user['role'] not in write_roles:
            context.add_error(self.ERROR_READONLY_FIELD)

    def _validate_attribute_data_relation(self, context):
        # TODO
        pass

    def _validate_attribute_unique(self, context):
        # return
        if not context.schema['unique']:
            return
        query = {context.field: context.value}
        old_document = context.additional_context.get('old_document', {})
        document_id = old_document.get('_id', None)
        if document_id:
            query['_id'] = {'$ne': document_id}
        resource_name = context.additional_context['resource'].name
        # import pdb; pdb.set_trace()
        if current_app.data.db[resource_name].find_one(query):
            context.add_error(self.ERROR_UNIQUE_FIELD % context.value)
