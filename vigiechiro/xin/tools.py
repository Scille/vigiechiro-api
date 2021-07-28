"""
    xin
    ~~~

    This module provides some generic tools extending Eve framework
"""

import json
import datetime
import bson
import hashlib
from werkzeug import Response
from flask import app, current_app, abort, request
from flask_pymongo import PyMongo
from bson.json_util import dumps
from werkzeug.routing import BaseConverter, ValidationError


def dict_projection(data, projection):
    opt_in = {k for k, v in projection.items() if not isinstance(v,dict) and v}
    opt_out = {k for k, v in projection.items() if not isinstance(v, dict) and not v}
    # If one field is opt in, all the filter is done by opt in
    if opt_in:
        # Remove all the fields except the opt in and the ones which
        # must be recursively checked (i.e. remove the fields marked as opt out
        # and the ones not mentioned in projection)
        data = {field: value for field, value in data.items()
                if projection.get(field, False) != False}
    else:
        data = {field: value for field, value in data.items()
                if field not in opt_out}
    # Recursively do the projection for the rest of the data
    for field in projection.keys() - opt_out - opt_in:
        if field in data:
            data[field] = dict_projection(data[field], projection[field])
    return data


class ObjectIdConverter(BaseConverter):
    """
        werkzeug converter to use ObjectId in url

        >>> from flask import Flask
        >>> app = Flask(__name__)
        >>> app.url_map.converters['objectid'] = ObjectIdConverter
        >>> @app.route('/objs/<objectid:object_id>')
        ... def route(object_id): return 'ok'
    """
    def to_python(self, value):
        converted = parse_id(value)
        if not converted:
            raise ValidationError()
        return converted

    def to_url(self, value):
        return str(value)


def str_to_date(string):
    """ Converts a date string formatted as defined in the configuration
        to the corresponding datetime value.

    :param string: the RFC-1123 string to convert to datetime value.
    """
    return datetime.datetime.strptime(string, current_app.config['DATE_FORMAT']) if string else None


def date_to_str(date):
    """ Converts a datetime value to the format defined in the configuration file.

    :param date: the datetime value to convert.
    """
    return datetime.datetime.strftime(date, current_app.config['DATE_FORMAT']) if date else None


# from flask import make_response, abort as flask_abort
# from flask.exceptions import JSONHTTPException


# def abort(status_code, errors=None, body=None, headers=None):
#     """Abort returning json format"""
#     if not body:
#         body = {}
#     if not headers:
#         headers = {}
#     headers['Content-type'] = 'application/json'
#     if errors:
#         body['_errors'] = errors if isinstance(errors, list) else [errors]
#     flask_abort(make_response(JSONHTTPException(body), status_code, headers))


def build_etag(value):
    h = hashlib.sha1()
    h.update(dumps(value, sort_keys=True).encode('utf-8'))
    return h.hexdigest()


def compare_objectid(id1, id2):
    id1 = ObjectId(id1) if not isinstance(id1, ObjectId) else id1
    id2 = ObjectId(id2) if not isinstance(id2, ObjectId) else id2
    return id1 == id2


class MongoJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        elif isinstance(obj, bson.ObjectId):
            return str(obj)
        elif isinstance(obj, set):
            return list(obj)
        elif hasattr(obj, "__iter__"):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


def jsonify(*args, **kwargs):
    """
        jsonify with support for MongoDB ObjectId
        (see: https://gist.github.com/akhenakh/2954605)
    """
    return Response(json.dumps(dict(*args, **kwargs), cls=MongoJsonEncoder),
                               mimetype='application/json')


def parse_id(obj_id):
    try:
        obj_id = bson.ObjectId(obj_id)
    except bson.errors.InvalidId:
        return None
    return obj_id
