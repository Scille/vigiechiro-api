"""
    Validator module
    ~~~~~~~~~~~~~~~~

    Rewrite of Cerberus schema validator
"""

import re
from flask import request, g, current_app
from bson import ObjectId
from datetime import datetime
from collections import Mapping, Sequence

from .tools import str_to_date, parse_id
from .snippets import get_resource
from .geo import (Point, MultiPoint, LineString, Polygon,
                  MultiLineString, MultiPolygon, GeometryCollection)


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
ERROR_STORAGE_TYPE = "'%s' must be stored as '%s' in database"
ERROR_UNIQUE_FIELD = "value '%s' is not unique"


def relation(resource, field='_id', expend=True, validator=None, **kwargs):
    """Data model template for a resource relation"""
    kwargs.update({'type': 'objectid',
                   'data_relation': {
                       'resource': resource,
                       'field': field,
                       'expend': expend,
                       'validator': validator
                   }
                   })
    return kwargs


def choice(choices, **kwargs):
    """Data model template for a regex choice"""
    kwargs.update({'type': 'string',
                   'regex': r'^({})$'.format('|'.join(choices))})
    return kwargs


class SchemaRunnerContext:
    """
        Context object used to push/pop state during schema run,
        and then provided as result
    """

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
        return '.'.join(f for f in [f for _, f, _ in self._stack[1:]] + [self.field]
                        if isinstance(f, str))

    def add_error(self, msg):
        self.is_valid = False
        path = self.get_current_path()
        if path not in self.errors:
            self.errors[path] = msg
        elif isinstance(self.errors[path], list):
            self.errors[path].append(msg)
        else:
            self.errors[path] = [self.errors[path], msg]


class SchemaRunnerException(Exception): pass


class SchemaRunner:
    def __init__(self, schema, partial=False):
        """
            :param schema: dict schema to run data against
            :param partial: SchemaRunner only contain a subset of the schema
        """
        self.schema = schema.copy()
        self.partial = partial

    def type(self, validate_function, serializer=None, name=None):
        """Decorator, register a validate type based on function name"""
        if not name:
            name = validate_function.__name__
        setattr(self, '_run_type_' + name, validate_function)
        setattr(self, '_run_serializer_type_' + name, serializer)

    def attribute(self, validate_function, name=None):
        """Decorator, register a validate attribute based on function name"""
        if not name:
            name = validate_function.__name__
        setattr(self, '_run_attribute_' + name, validate_function)

    def run(self, document, is_update=False, additional_context=None):
        context = SchemaRunnerContext({'type': 'dict', 'schema': self.schema},
                                      document, is_update=is_update,
                                      additional_context=additional_context)
        self._run_schema(context)
        return context

    def _run_schema(self, context):
        # A schema must containt a type, which is guaranteed to be applied first
        if 'type' not in context.schema:
            raise SchemaRunnerException('{} : schema must contain a `type`'.format(
                context.get_current_path()))
        self._run_attribute_type(context)
        # Apply the rest of the attributes
        for attribute in context.schema.keys():
            if attribute == 'type':
                continue
            validate_attribute = getattr(self, "_run_attribute_" + attribute, None)
            if not validate_attribute:
                if self.partial:
                    continue
                raise SchemaRunnerException('{} : unknown attribute `{}`'.format(
                    context.get_current_path(), attribute))
            validate_attribute(context)

    def _run_attribute_type(self, context):
        type_name = context.schema['type']
        # Retrieve the validate function among object's methods
        validate_type = getattr(self, "_run_type_" + type_name, None)
        if not validate_type:
            if self.partial:
                return
            raise SchemaRunnerException('{} : unknown type `{}`'.format(
                context.get_current_path(), type_name))
        validate_type(context)

    def _run_type_dict(self, context):
        if not isinstance(context.value, dict):
            context.add_error(ERROR_BAD_TYPE % 'dict')
            return
        # Check for unexpected fields
        dict_schema = context.schema.get('schema', None)
        dict_keyschema = context.schema.get('keyschema', None)
        if not dict_schema and not dict_keyschema:
            raise SchemaRunnerException('Dict must have a `schema` or a `keyschema` attribute')
        if dict_schema and dict_keyschema:
            raise SchemaRunnerException('Dict cannot have both `schema` or `keyschema` attributes')
        if dict_schema:
            dict_schema_keys = set(dict_schema.keys())
            value_keys = set(context.value.keys())
            unexpected_fiels = value_keys - dict_schema_keys
            for field in unexpected_fiels:
                value = context.value.pop(field)
                context.push(None, field, value)
                context.add_error(ERROR_UNKNOWN_FIELD)
                context.pop()
            # Check for missing required fields
            if not context.is_update:
                missing_fields = dict_schema_keys - value_keys
                for field in missing_fields:
                    if dict_schema[field].get('required', False):
                        context.push(dict_schema[field], field, None)
                        context.add_error(ERROR_REQUIRED_FIELD)
                        context.pop()
            # Now recursively validate each field
            for field, value in context.value.items():
                context.push(dict_schema[field], field, value)
                self._run_schema(context)
                context.pop()
            # If a field containe None as value, it should be skipped
            no_none_dict = {k: v for k, v in context.value.items() if v != None}
            if len(context._stack) > 0:
                s, f, v = context.pop()
                context.value[f] = no_none_dict
                context.push(s, f, no_none_dict)
            else:
                context.value = context.document = no_none_dict
        if dict_keyschema:
            # Just recursively validate each sub item
            for field, value in context.value.items():
                context.push(dict_keyschema, field, value)
                self._run_schema(context)
                context.pop()

    def _run_type_list(self, context):
        if not isinstance(context.value, list):
            context.add_error(ERROR_BAD_TYPE % 'list')
            return
        list_schema = context.schema.get('schema', None)
        if not list_schema:
            raise SchemaRunnerException('List must have a `schema` attribute')
        for i, elem in enumerate(context.value):
            context.push(list_schema, i, elem)
            self._run_schema(context)
            context.pop()


class Unserializer(SchemaRunner):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, partial=True, **kwargs)

    def run(self, *args, **kwargs):
        # Given the retrieved document can retrieved with a projection
        # (i.e. partial document), we should not check for missing fields
        if 'is_update' not in kwargs:
            kwargs['is_update'] = True
        return super().run(*args, **kwargs)

    def _run_type_set(self, context):
        set_schema = context.schema.get('schema', None)
        if not set_schema:
            raise SchemaRunnerException('Set must have a `schema` attribute')
        if isinstance(context.value, list):
            unserialized = set(context.value)
            schema, field, _ = context.pop()
            context.value[field] = unserialized
            context.push(schema, field, unserialized)
            for i, elem in enumerate(context.value):
                context.push(set_schema, i, elem)
                self._run_schema(context)
                context.pop()
        else:
            context.add_error(ERROR_STORAGE_TYPE % ('set', 'list'))

    def _run_attribute_hidden(self, context):
        """Remove current element from the unserialized document"""
        # Don't hide the element if we are in internal mode or if the
        # field is explicitly specified in the additional_context
        if context.additional_context.get('internal', False):
            return
        hidden_additional = context.additional_context.get('hidden', {})
        if not hidden_additional.get(context.get_current_path(), True):
            return
        if context.schema['hidden']:
            schema, field, _ = context.pop()
            context.value[field] = None
            context.push(schema, field, None)

    def _run_attribute_expend(self, context):
        # Stub, handled in `_run_attribute_data_relation`
        pass

    def _run_attribute_data_relation(self, context):
        if not isinstance(context.value, ObjectId):
            context.add_error(ERROR_STORAGE_TYPE % ('data_relation', 'objectid'))
            return
        data_relation = context.schema['data_relation']
        # Expend relation if asked for
        expend_additional = context.additional_context.get('expend', {})
        if isinstance(expend_additional, dict):
            expend = expend_additional.get(context.get_current_path(), data_relation.get('expend', False))
        else:
            expend = expend_additional
        if expend:
            resource_name = data_relation.get('resource', None)
            field = data_relation.get('field', None)
            projection = data_relation.get('projection', None)
            if not resource_name or not field:
                raise SchemaRunnerException("`data_relation` requires"
                                            " `field` and `resource` fiels")
            data_relation = get_resource(resource_name, context.value, field=field,
                                         projection=projection, auto_abort=False)
            if not data_relation:
                context.add_error("value '%s' must exist in resource"
                                  " '%s', field '%s'." %
                                  (context.value, resource_name, field))
            else:
                from ..resources import strip_resource_fields
                data_relation = strip_resource_fields(resource_name, data_relation)
                schema, field, _ = context.pop()
                context.value[field] = data_relation
                context.push(schema, field, data_relation)


class GenericValidator(SchemaRunner):

    def __init__(self, schema):
        super().__init__(schema)
        # Dynamic init of generic types
        self._run_type_factory(int, 'integer')
        self._run_type_factory(str, 'string')
        self._run_type_factory(bool, 'boolean')

    def _run_type_factory(self, type, type_name):
        def validate(context):
            if not isinstance(context.value, type):
                context.add_error(ERROR_BAD_TYPE % type_name)
        setattr(self, '_run_type_' + type_name, validate)

    def _run_type_float(self, context):
        if (not isinstance(context.value, float) and
            not isinstance(context.value, int)):
            context.add_error(ERROR_BAD_TYPE % 'float')

    def _run_attribute_readonly(self, context):
        if context.schema['read_only']:
            context.add_error(ERROR_READONLY_FIELD)

    def _run_attribute_hidden(self, context):
        """Consider the current element as unknown"""
        # Don't hide the element if we are in internal mode or if the
        # field is explicitly specified in the additional_context
        if context.additional_context.get('internal', False):
            return
        hidden_additional = context.additional_context.get('hidden', {})
        if not hidden_additional.get(context.get_current_path(), True):
            return
        if context.schema['hidden']:
            context.add_error(ERROR_UNKNOWN_FIELD)

    def _run_attribute_regex(self, context):
        regex = context.schema['regex']
        pattern = re.compile(regex)
        if not isinstance(context.value, str):
            context.add_error(ERROR_BAD_TYPE % 'string')
        elif not pattern.match(context.value):
            context.add_error(ERROR_REGEX % regex)

    def _run_type_datetime(self, context):
        # If value is not a datetime object, try to unserialize it
        if isinstance(context.value, str):
            # If the unserialized succeed, update the context stack
            try:
                unserialized = str_to_date(context.value)
            except ValueError:
                context.add_error(ERROR_BAD_TYPE % "datetime")
                return
            if unserialized:
                schema, field, _ = context.pop()
                context.value[field] = unserialized
                context.push(schema, field, unserialized)
        if not isinstance(context.value, datetime):
            context.add_error(ERROR_BAD_TYPE % "datetime")

    def _run_type_objectid(self, context):
        # If value is not a ObjectId object, try to convert it
        if isinstance(context.value, str):
            # If the conversion succeed, update the context stack
            unserialized = parse_id(context.value)
            if unserialized:
                schema, field, _ = context.pop()
                context.value[field] = unserialized
                context.push(schema, field, unserialized)
        if not isinstance(context.value, ObjectId):
            context.add_error(ERROR_BAD_TYPE % 'ObjectId')

    def _run_type_url(self, context):
        """Basic url regex filter"""
        if not isinstance(context.value, str):
            context.add_error(ERROR_BAD_TYPE % 'string')
        elif not re.match(r"^https?://", context.value):
            context.add_error(ERROR_BAD_TYPE % 'url')

    def _run_attribute_maxlength(self, context):
        max_length = context.schema['maxlength']
        if isinstance(context.value, Sequence):
            if len(context.value) > max_length:
                context.add_error(ERROR_MAX_LENGTH % max_length)

    def _run_attribute_minlength(self, context):
        min_length = context.schema['minlength']
        if isinstance(context.value, Sequence):
            if len(context.value) < min_length:
                context.add_error(ERROR_MIN_LENGTH % min_length)

    def _run_attribute_max(self, context):
        max = context.schema['max']
        if isinstance(context.value, (int, float)):
            if context.value > max:
                context.add_error(ERROR_MAX_VALUE % max)

    def _run_attribute_min(self, context):
        min = context.schema['min']
        if isinstance(context.value, (int, float)):
            if context.value < min:
                context.add_error(ERROR_MIN_VALUE % min)

    def _run_attribute_allowed(self, context):
        allowed_values = context.schema['allowed']
        if isinstance(context.value, str):
            if context.value not in allowed_values:
                context.add_error(ERROR_UNALLOWED_VALUE % context.value)
        elif isinstance(context.value, Sequence):
            disallowed = set(context.value) - set(allowed_values)
            if disallowed:
                context.add_error(ERROR_UNALLOWED_VALUES % list(disallowed))
        elif isinstance(context.value, int):
            if context.value not in allowed_values:
                context.add_error(ERROR_UNALLOWED_VALUE % context.value)

    def _run_attribute_empty(self, context):
        empty = context.schema['empty']
        if isinstance(context.value, str) and len(context.value) == 0 and not empty:
            context.add_error(ERROR_EMPTY_NOT_ALLOWED)

    def _run_attribute_schema(self, context):
        # Stub, schema is handled in `_run_type_list` and
        # `_run_type_dict`
        pass

    def _run_attribute_keyschema(self, context):
        # Stub, keyschema is handled in `_run_type_dict`
        pass

    def _run_attribute_required(self, context):
        # Stub, required is handled in `_run_type_dict`
        pass

    def _run_type_set(self, context):
        set_schema = context.schema.get('schema', None)
        if not set_schema:
            raise SchemaRunnerException('Set must have a `schema` attribute')
        error = lambda: context.add_error(ERROR_BAD_TYPE % 'set')
        if isinstance(context.value, set):
            # Given set is not supported in mongodb, it is stored as a list
            serialized = list(context.value)
            schema, field, _ = context.pop()
            context.value[field] = serialized
            context.push(schema, field, serialized)
        elif isinstance(context.value, list):
            # Try to convert list into set then make sure it's
            # a valid set (i.e. each element is unique)
            try:
                set_value = set(context.value)
                # Make sure we didn't loose any element
                if len(set_value) != len(context.value):
                    return error()
            except TypeError:
                return error()
        else:
            # No other convertion possible...
            return error()
        for i, elem in enumerate(context.value):
            context.push(set_schema, i, elem)
            self._run_schema(context)
            context.pop()

    def _run_type_geometrycollection(self, context):
        try:
            GeometryCollection(context.value)
        except TypeError:
            context.add_error("GeometryCollection not correct" % context.value)

    def _run_type_point(self, context):
        try:
            Point(context.value)
        except TypeError as e:
            context.add_error("Point not correct %s: %s" % (value, e))

    def _run_type_linestring(self, context):
        try:
            LineString(context.value)
        except TypeError:
            context.add_error("LineString not correct %s " % value)

    def _run_type_polygon(self, field, value):
        try:
            Polygon(value)
        except TypeError:
            context.add_error("LineString not correct %s " % value)

    def _run_type_multipoint(self, field, value):
        try:
            MultiPoint(value)
        except TypeError:
            context.add_error("MultiPoint not correct" % value)

    def _run_type_multilinestring(self, field, value):
        try:
            MultiLineString(value)
        except TypeError:
            context.add_error("MultiLineString not  correct" % value)

    def _run_type_multipolygon(self, field, value):
        try:
            MultiPolygon(value)
        except TypeError:
            context.add_error("MultiPolygon not  correct" % value)


class Validator(GenericValidator):

    def _run_attribute_postonly(self, context):
        """Field can be altered by non-admin during POST only"""
        post_only = context.schema['postonly']
        try:
            request_user = g.request_user
        except AttributeError:
            # Not in a request, we are most likely in a batch job
            return
        if request_user['role'] == 'Administrateur':
            return
        if post_only and request.method != 'POST':
            context.add_error(ERROR_READONLY_FIELD)

    def _run_attribute_writerights(self, context):
        """Limit write rights to write_roles"""
        write_roles = context.schema['writerights']
        if isinstance(write_roles, str):
            write_roles = [write_roles]
        try:
            request_user = g.request_user
        except AttributeError:
            # Not in a request, we are most likely in a batch job
            return
        if request_user['role'] not in write_roles:
            context.add_error(ERROR_READONLY_FIELD)

    def _run_type_objectid(self, context):
        # If value is not a ObjectId object, try to convert it
        if isinstance(context.value, dict) and 'data_relation' in context.schema:
            # value is expended data_relation, will be shrinked by attribute
            return
        if isinstance(context.value, str):
            # If the conversion succeed, update the context stack
            unserialized = parse_id(context.value)
            if unserialized:
                schema, field, _ = context.pop()
                context.value[field] = unserialized
                context.push(schema, field, unserialized)
        if not isinstance(context.value, ObjectId):
            context.add_error(ERROR_BAD_TYPE % 'ObjectId')

    def _run_attribute_expend(self, context):
        # Stub, handled in `_run_attribute_data_relation`
        pass

    def _run_attribute_data_relation(self, context):
        # Relation should be stored as an objectid pointing on a valid resource
        if context.schema['type'] != 'objectid':
            raise SchemaRunnerException("data_relation attribute"
                                        " requires type `objectid`")
        data_relation = context.schema['data_relation']
        resource_name = data_relation.get('resource', None)
        field = data_relation.get('field', None)
        if not resource_name or not field:
            raise SchemaRunnerException("data_relation requires"
                                        " `field` and `resource` fiels")
        if isinstance(context.value, dict):
            # Expended data relation, assume the relation must then exist
            # and reshrink it
            serialized = context.value.get(field, None)
            if not isinstance(serialized, ObjectId):
                context.add_error("missing field `{}` to shrink"
                                  " data_relation".format(field))
            schema, field, data_relation = context.pop()
            context.value[field] = serialized
            context.push(schema, field, serialized)
        else:
            data_relation = get_resource(resource_name, context.value,
                                         field=field, auto_abort=False)
            if not data_relation:
                context.add_error("value '%s' must exist in resource"
                                  " '%s', field '%s'." %
                                  (context.value, resource_name, field))
        if data_relation and 'validator' in data_relation:
            error = data_relation['validator'](context, data_relation)
            if error:
                context.add_error(error)


    def _run_attribute_unique(self, context):
        if not context.schema['unique']:
            return
        query = {context.field: context.value}
        old_document = context.additional_context.get('old_document', {})
        document_id = old_document.get('_id', None)
        if document_id:
            query['_id'] = {'$ne': document_id}
        resource_name = context.additional_context['resource'].name
        if current_app.data.db[resource_name].find_one(query):
            context.add_error(ERROR_UNIQUE_FIELD % context.value)
