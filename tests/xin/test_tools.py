import pytest

from vigiechiro.xin.tools import dict_projection


class Test_dict_projection:

    def test_empty_projection(self):
        data = {'a': 1, 'b': 2}
        projection = {}
        assert dict_projection(data, projection) == data


    def test_empty_data(self):
        projection = {'a': True, 'b': True}
        data = {}
        assert dict_projection(data, projection) == data


    def test_opt_in(self):
        projection = {'a': True, 'b': True}
        data = {'a': 'data', 'b': 'other'}
        assert dict_projection(data, projection) == data
        data = {'a': 'data', 'b': 'other', 'c': 'leaveme'}
        assert dict_projection(data, projection) == {'a': 'data', 'b': 'other'}
        data = {'b': 'other', 'c': 'leaveme'}
        assert dict_projection(data, projection) == {'b': 'other'}


    def test_opt_out(self):
        projection = {'a': False, 'b': False}
        data = {'a': 'data', 'b': 'other'}
        assert dict_projection(data, projection) == {}
        data = {'a': 'data', 'b': 'other', 'c': 'survivor'}
        assert dict_projection(data, projection) == {'c': 'survivor'}
        data = {'a': 'data', 'c': 'survivor'}
        assert dict_projection(data, projection) == {'c': 'survivor'}


    def test_opt_mixed(self):
        projection = {'a': True, 'b': False}
        data = {'a': 'data', 'b': 'killme'}
        assert dict_projection(data, projection) == {'a': 'data'}
        data = {'a': 'data', 'b': 'killme', 'c': 'implicitkill'}
        assert dict_projection(data, projection) == {'a': 'data'}


    def test_recursive(self):
        projection = {'b': {'bb': False}}
        data = {'a': 'data', 'b': {'bb': 'killme', 'ba': 'stillhere'}}
        assert dict_projection(data, projection) == {'a': 'data', 'b': {'ba': 'stillhere'}}
        projection = {'b': False}
        assert dict_projection(data, projection) == {'a': 'data'}
        projection = {'b': {'bb': True}}
        data = {'a': 'data', 'b': {'bb': 'stillhere', 'ba': 'implicitkill'}}
        assert dict_projection(data, projection) == {'a': 'data', 'b': {'bb': 'stillhere'}}
        projection = {'b': {}}
        data = {'a': 'data', 'b': {'bb': 'stillhere'}}
        assert dict_projection(data, projection) == {'a': 'data', 'b': {'bb': 'stillhere'}}
        projection = {'a': False, 'b': {}}
        data = {'a': 'killme', 'b': {'bb': 'stillhere'}}
        assert dict_projection(data, projection) == {'b': {'bb': 'stillhere'}}
