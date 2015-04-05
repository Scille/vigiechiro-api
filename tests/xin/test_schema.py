import pytest
from datetime import datetime
from bson import ObjectId
from copy import deepcopy

from vigiechiro import app
from vigiechiro.xin.schema import GenericValidator, Validator, Unserializer

from ..common import db

TEST_RESOURCE = __name__


@pytest.fixture
def clean_db(request):
    def finalizer():
        db[TEST_RESOURCE].remove()
    request.addfinalizer(finalizer)
    return None


def with_flask_context(f):
    def decorator(*args, **kwargs):
        with app.test_request_context():
            return f(*args, **kwargs)
    return decorator


def test_basic_validation():
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
    @with_flask_context
    def test():
        result = v.run({'a': 1, 'b': 'touille', 'c': {}})
        assert result.is_valid, result.errors
        result = v.run({'a': 1, 'b': 'touille', 'c': {'ca': []}})
        assert result.is_valid, result.errors
        result = v.run({'a': 1, 'b': 'touille', 'c': {'ca': [1, 2, 3]}})
        assert result.is_valid, result.errors
        result = v.run({'a': 1, 'b': 'touille', 'c': {'ca': [1, 2, '3']}})
        assert not result.is_valid, result.errors
        result = v.run({'a': '1', 'b': 'touille', 'c': {}})
        assert not result.is_valid, result.errors
        result = v.run({'a': 1, 'b': 0, 'c': {}})
        assert not result.is_valid, result.errors
        result = v.run({'a': {}, 'b': 0, 'c': {}})
        assert not result.is_valid, result.errors
        result = v.run({'a': 1, 'b': 'touille', 'c': {}, 'd': 1})
        assert not result.is_valid, result.errors
        result = v.run({'a': 1, 'b': 'touille', 'c': {}, 'd': 1})
        assert not result.is_valid, result.errors
        result = v.run({'serialized': 'Fri, 23 Nov 2012 08:11:19 GMT'})
        assert result.is_valid, result.errors
    test()


def test_serialize():
    schema = {
        '_id': {'type': 'objectid'},
        's': {'type': 'datetime'}
    }
    v = GenericValidator(schema)
    @with_flask_context
    def test():
        result = v.run({'_id': '54ba464f1d41c83768e76fbf',
                             's': 'Fri, 23 Nov 2012 08:11:19 GMT'})
        assert result.is_valid, result.errors
        assert isinstance(result.document['_id'], ObjectId)
        assert isinstance(result.document['s'], datetime)
        # Serialize operation should be idempotent
        result = v.run(result.document)
        assert isinstance(result.document['_id'], ObjectId)
        assert isinstance(result.document['s'], datetime)
        assert result.is_valid, result.errors
    test()


def test_bad_serialized():
    schema = {
        '_id': {'type': 'objectid'},
        's': {'type': 'datetime'}
    }
    v = GenericValidator(schema)
    valid_doc = {'_id': '54ba464f1d41c83768e76fbf',
                 's': 'Fri, 23 Nov 2012 08:11:19 GMT'}
    @with_flask_context
    def test():
        bad_doc = deepcopy(valid_doc)
        for dummy in ['54ba464f1d41c83768e76', '54ba464f1d41c83768e76fbffff',
                      '', 'dummy']:
            bad_doc['_id'] = dummy
            result = v.run(bad_doc)
            assert not result.is_valid, result
        bad_doc = deepcopy(valid_doc)
        for dummy in ['Fri, 33 Nov 2012 08:11:19 GMT', '1423751527', ''
                      'Wed, 33 Nov 2012 08:11:19 GMT']:
            bad_doc['_id'] = dummy
            result = v.run(bad_doc)
            assert not result.is_valid, result
    test()


def test_bad_types():
    schema = {
        'f_integer': {'type': 'boolean'},
        'f_boolean': {'type': 'integer'},
        'f_float': {'type': 'float'}
    }
    v = GenericValidator(schema)
    valid_doc = {
        'f_integer': 42,
        'f_boolean': True,
        'f_float': 3.14
    }
    @with_flask_context
    def test():
        bad_doc = deepcopy(valid_doc)
        for dummy in ['string', 3.14, '']:
            bad_doc['f_integer'] = dummy
            result = v.run(bad_doc)
            if result.is_valid:
                return False, 'Bad type accepted for integer: {}'.format(dummy)
        bad_doc = deepcopy(valid_doc)
        for dummy in ['string', 3.14, 1, '']:
            bad_doc['f_boolean'] = dummy
            result = v.run(bad_doc)
            if result.is_valid:
                return False, 'Bad type accepted for boolean: {}'.format(dummy)
        bad_doc = deepcopy(valid_doc)
        for dummy in ['string', '']:
            bad_doc['f_float'] = dummy
            result = v.run(bad_doc)
            if result.is_valid:
                return False, 'Bad type accepted for float: {}'.format(dummy)
        return True, ''
    result, msg = test()
    assert result, msg


def test_required_fields():
    schema = {
        # Add automatically added fields to prevent "unknown field" errors
        'r': {'type': 'string', 'required': True},
        'nr': {'type': 'string', 'required': False}
    }
    v = GenericValidator(schema)
    @with_flask_context
    def test():
        valid_docs = [
            {'r': 'data', 'nr': 'data'},
            {'r': 'data'}
        ]
        for doc in valid_docs:
            result = v.run(doc)
            assert result.is_valid, result
        invalid_docs = [
            {'nr': 'data'},
            {}
        ]
        for doc in invalid_docs:
            result = v.run(doc)
            assert not result.is_valid, result
        # During update, missing required fields is ok
        for doc in invalid_docs:
            result = v.run(doc, is_update=True)
            assert result.is_valid, result
    test()


def test_data_relation(clean_db):
    vigiechiro_db = db[TEST_RESOURCE]
    relation_to_id = vigiechiro_db.insert({'a': 1, 'b': 'b'})
    doc_id = vigiechiro_db.insert({'r': relation_to_id, 'x': 1})
    schema = {
        '_id': {'type': 'objectid'},
        'r': {'type': 'objectid', 'data_relation': {'resource': TEST_RESOURCE, 'field': '_id'}},
        'x': {'type': 'integer'}
    }
    u = Unserializer(schema)
    @with_flask_context
    def test():
        doc = vigiechiro_db.find_one({'_id': doc_id})
        result = u.run(deepcopy(doc))
        assert result.is_valid, result.errors
        # Same but ask for data_relation expension
        schema['r']['data_relation']['expend'] = True
        result = u.run(deepcopy(doc))
        assert result.is_valid, result.errors
        assert result.document['r'] == vigiechiro_db.find_one({'_id': relation_to_id})
        # Test with projection
        projection = {'b': 1}
        schema['r']['data_relation']['projection'] = projection
        result = u.run(deepcopy(doc))
        assert result.is_valid, result.errors
        assert (result.document['r'] ==
                vigiechiro_db.find_one({'_id': relation_to_id}, projection))
    test()


def test_nested_data_relation(clean_db):
    vigiechiro_db = db[TEST_RESOURCE]
    relation_to_id = vigiechiro_db.insert({'a': 1, 'b': 'b'})
    doc_id = vigiechiro_db.insert({
        'n': {
            'nested_dict': {'r': relation_to_id},
            'nested_list': [relation_to_id, relation_to_id],
        }
    })
    schema = {
        '_id': {'type': 'objectid'},
        'n': {
            'type': 'dict',
            'schema': {
                'nested_dict': {
                    'type': 'dict',
                    'schema': {
                        'r': {
                            'type': 'objectid',
                            'data_relation': {'resource': TEST_RESOURCE, 'field': '_id'}
                        }
                    }
                },
                'nested_list': {
                    'type': 'list',
                    'schema': {
                        'type': 'objectid',
                        'data_relation': {'resource': TEST_RESOURCE, 'field': '_id'}
                    }
                }
            }
        }
    }
    v = Unserializer(schema)
    @with_flask_context
    def test():
        relation_data = vigiechiro_db.find_one({'_id': relation_to_id})
        doc = vigiechiro_db.find_one({'_id': doc_id})
        result = v.run(deepcopy(doc))
        assert result.is_valid, result.errors
        # Same but ask for dict data_relation expension
        schema['n']['schema']['nested_dict']['schema']['r']['data_relation']['expend'] = True
        result = v.run(deepcopy(doc))
        expected_dict = {'r': relation_data}
        expected = deepcopy(doc)
        expected['n']['nested_dict'] = expected_dict
        assert result.is_valid, result.errors
        assert result.document == expected
        # Same but ask for list data_relation expension
        del schema['n']['schema']['nested_dict']['schema']['r']['data_relation']['expend']
        schema['n']['schema']['nested_list']['schema']['data_relation']['expend'] = True
        result = v.run(deepcopy(doc))
        expected_list = [relation_data, relation_data]
        expected = deepcopy(doc)
        expected['n']['nested_list'] = expected_list
        assert result.is_valid, result.errors
        assert result.document == expected
        # Test both at the same time
        schema['n']['schema']['nested_dict']['schema']['r']['data_relation']['expend'] = True
        schema['n']['schema']['nested_list']['schema']['data_relation']['expend'] = True
        result = v.run(deepcopy(doc))
        assert result.is_valid, result.errors
        expected = deepcopy(doc)
        expected['n'] = {'nested_dict': expected_dict, 'nested_list': expected_list}
        assert result.document == expected
    test()


def test_bijection_set():
    schema = {'s': {'type': 'set', 'schema': {'type': 'integer'}}}
    u = Unserializer(schema)
    v = GenericValidator(schema)
    data = {'s': {1, 2, 3}}
    result = v.run(deepcopy(data))
    assert result.is_valid, result.errors
    result = u.run(result.document)
    assert result.is_valid, result.errors
    assert result.document == data


def test_bijection_data_relation(clean_db):
    vigiechiro_db = db[TEST_RESOURCE]
    relation_to_id = vigiechiro_db.insert({'a': 1, 'b': 'b'})
    assert relation_to_id
    doc_id = vigiechiro_db.insert({'r': relation_to_id})
    assert doc_id
    # Test bijection for data relation
    schema = {
            '_id': {'type': 'objectid'},
            'r': {
                    'type': 'objectid',
                    'data_relation': {'resource': TEST_RESOURCE, 'field': '_id',
                                      'expend': True}
                }
            }
    @with_flask_context
    def test():
        u = Unserializer(schema)
        v = Validator(schema)
        doc = vigiechiro_db.find_one({'_id': doc_id})
        result = u.run(deepcopy(doc))
        print(result.document)
        assert result.is_valid, result.errors
        expected = deepcopy(doc)
        expected['r'] = vigiechiro_db.find_one({'_id': relation_to_id})
        assert result.document == expected
        result = v.run(result.document)
        assert result.is_valid, result.errors
        assert result.document == doc
    test()
