"""
    xin
    ~~~

    This module provides some generic tools extending Eve framework
"""

from .blueprint import EveBlueprint
from .validator import Validator

import json
import datetime
from werkzeug import Response
from bson import ObjectId


def compare_objectid(id1, id2):
    id1 = ObjectId(id1) if not isinstance(id1, ObjectId) else id1
    id2 = ObjectId(id2) if not isinstance(id2, ObjectId) else id2
    return id1 == id2


class MongoJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        elif isinstance(obj, ObjectId):
            return str(obj)
        return json.JSONEncoder.default(self, obj)


def jsonify(*args, **kwargs):
    """
        jsonify with support for MongoDB ObjectId
        (see: https://gist.github.com/akhenakh/2954605)
    """
    return Response(json.dumps(dict(*args, **kwargs), cls=MongoJsonEncoder),
                               mimetype='application/json')
