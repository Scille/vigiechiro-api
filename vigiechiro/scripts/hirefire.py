"""
The Flask middleware provided as a Blueprint exposing the the URL paths
HireFire requires. Implements the test response and the json response
that contains the procs data.
"""

from __future__ import absolute_import
from flask import Blueprint, jsonify, current_app
import json
import os

from hirefire import procs
from hirefire.utils import TimeAwareJSONEncoder


loaded_procs = None
def get_loaded_procs():
    if not loaded_procs:
        TOKEN = current_app.config.get('HIREFIRE_TOKEN', 'development')
        PROCS = current_app.config.get('HIREFIRE_PROCS', [])
        if not PROCS:
            raise RuntimeError('The HireFire Flask middleware requires at least '
                               'one proc defined in the HIREFIRE_PROCS setting.')
        loaded_procs = procs.load_procs(*PROCS)
    return loaded_procs


hirefire = Blueprint(__name__, 'hirefire')


@hirefire.route('/hirefire/test/')
def test():
    """
    Doesn't do much except telling the HireFire bot it's installed.
    """
    return 'HireFire Middleware Found!'


@hirefire.route('/hirefire/<id>/info')
def info(id):
    """
    The heart of the app, returning a JSON ecoded list
    of proc results.
    """
    data = []
    for name, proc in get_loaded_procs().items():
        data.append({
            'name': name,
            'quantity': proc.quantity() or 'null',
        })
    payload = json.dumps(data,
                         cls=TimeAwareJSONEncoder,
                         ensure_ascii=False)
    return jsonify(payload)

from flask import request
from .test import add

@hirefire.route('/hirefire/add')
def add_route():
    x = int(request.args.get('x', 0))
    y = int(request.args.get('y', 0))
    add.delay(x, y)
    return 'wait for it...'
