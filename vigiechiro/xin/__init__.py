"""
    xin
    ~~~

    This module provides some generic tools extending Eve framework
"""

from .blueprint import EveBlueprint
from .validator import Validator

from bson import ObjectId


def compare_objectid(id1, id2):
    id1 = ObjectId(id1) if not isinstance(id1, ObjectId) else id1
    id2 = ObjectId(id2) if not isinstance(id2, ObjectId) else id2
    return id1 == id2
