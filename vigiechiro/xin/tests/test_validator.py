import pytest
from datetime import datetime
from bson import ObjectId

from vigiechiro import app
from vigiechiro.xin.validator import GenericValidator


@pytest.fixture
def flask_context():
    return app.test_request_context()


def test_basic_validation(flask_context):
    schema = {
        'a': {'type': 'integer'},
        'b': {'type': 'string'},
        'c': {
            'type': 'dict',
            'schema': {
                'ca': {
                    'type': 'list',
                    'schema': {
                        'type': 'integer'
                    }
                }
            }
        },
        'serialized': {'type': 'datetime'}
    }
    v = GenericValidator(schema)
    with flask_context:
        result = v.validate({'a': 1, 'b': 'touille', 'c': {}})
        assert result.is_valid, result.errors
        result = v.validate({'a': 1, 'b': 'touille', 'c': {'ca': []}})
        assert result.is_valid, result.errors
        result = v.validate({'a': 1, 'b': 'touille', 'c': {'ca': [1, 2, 3]}})
        assert result.is_valid, result.errors
        result = v.validate({'a': 1, 'b': 'touille', 'c': {'ca': [1, 2, '3']}})
        assert not result.is_valid, result.errors
        result = v.validate({'a': '1', 'b': 'touille', 'c': {}})
        assert not result.is_valid, result.errors
        result = v.validate({'a': 1, 'b': 0, 'c': {}})
        assert not result.is_valid, result.errors
        result = v.validate({'a': {}, 'b': 0, 'c': {}})
        assert not result.is_valid, result.errors
        result = v.validate({'a': 1, 'b': 'touille', 'c': {}, 'd': 1})
        assert not result.is_valid, result.errors
        result = v.validate({'a': 1, 'b': 'touille', 'c': {}, 'd': 1})
        assert not result.is_valid, result.errors
        result = v.validate({'serialized': 'Fri, 23 Nov 2012 08:11:19 GMT'})
        assert result.is_valid, result.errors


def test_serialized(flask_context):
    schema = {
        '_id': {'type': 'objectid'},
        's': {'type': 'datetime'}
    }
    v = GenericValidator(schema)
    with app.test_request_context() as c:
        result = v.validate({'_id': '54ba464f1d41c83768e76fbf',
                             's': 'Fri, 23 Nov 2012 08:11:19 GMT'})
        assert result.is_valid, result.errors
        assert isinstance(result.document['_id'], ObjectId)
        assert isinstance(result.document['s'], datetime)
        # Unserialize operation should be idempotent
        result = v.validate(result.document)
        assert isinstance(result.document['_id'], ObjectId)
        assert isinstance(result.document['s'], datetime)
        assert result.is_valid, result.errors


def test_bad_serialized(flask_context):
    schema = {
        '_id': {'type': 'objectid'},
        's': {'type': 'datetime'}
    }
    v = GenericValidator(schema)
    valid_doc = {'_id': '54ba464f1d41c83768e76fbf',
                 's': 'Fri, 23 Nov 2012 08:11:19 GMT'}
    with flask_context:
        bad_doc = valid_doc.copy()
        for dummy in ['54ba464f1d41c83768e76', '54ba464f1d41c83768e76fbffff',
                      '', 'dummy']:
            bad_doc['_id'] = dummy
            result = v.validate(bad_doc)
            assert not result.is_valid, result
        bad_doc = valid_doc.copy()
        for dummy in ['Fri, 33 Nov 2012 08:11:19 GMT', '1423751527', ''
                      'Wed, 33 Nov 2012 08:11:19 GMT']:
            bad_doc['_id'] = dummy
            result = v.validate(bad_doc)
            assert not result.is_valid, result


def test_required_fields(flask_context):
    schema = {
        'r': {'type': 'string', 'required': True},
        'nr': {'type': 'string', 'required': False}
    }
    v = GenericValidator(schema)
    with flask_context:
        valid_docs = [
            {'r': 'data', 'nr': 'data'},
            {'r': 'data'}
        ]
        for doc in valid_docs:
            result = v.validate(doc)
            assert result.is_valid, result
        invalid_docs = [
            {'nr': 'data'},
            {}
        ]
        for doc in invalid_docs:
            result = v.validate(doc)
            assert not result.is_valid, result
        # During update, missing required fields is ok
        for doc in invalid_docs:
            result = v.validate(doc, is_update=True)
            assert result.is_valid, result


# def test_types_validation():
#         schema = {
#         'a': {'type': 'integer'},
#         'b': {'type': 'string'},
#         'c': {'type': 'float'},
#         'd': {'type': 'datetime'},
#         'c': {
#             'type': 'dict',
#             'schema': {
#                 'ca': {
#                     'type': 'list',
#                     'schema': {
#                         'type': 'integer'
#                     }
#                 }
#             }
#         },
#         'serialized': {'type': 'datetime'}
#     }