"""
The Flask middleware provided as a Blueprint exposing the the URL paths
HireFire requires. Implements the test response and the json response
that contains the procs data.
"""

from __future__ import absolute_import
from flask import Blueprint, Response, current_app
import json
import os

from hirefire.procs import load_procs
from hirefire.utils import TimeAwareJSONEncoder


def build_hirefire_blueprint(token, procs):
    if not procs:
        raise RuntimeError('The HireFire Flask middleware requires at least '
                           'one proc defined in the HIREFIRE_PROCS setting.')
    loaded_procs = load_procs(*procs)
    bp = Blueprint(__name__, 'hirefire')

    @bp.route('/hirefire/test/')
    def test():
        """
        Doesn't do much except telling the HireFire bot it's installed.
        """
        return 'HireFire Middleware Found!'


    @bp.route('/hirefire/<id>/info')
    def info(id):
        """
        The heart of the app, returning a JSON ecoded list
        of proc results.
        """
        data = []
        for name, proc in loaded_procs.items():
            data.append({
                'name': name,
                'quantity': proc.quantity() or 'null',
            })
        return Response(json.dumps(data, cls=TimeAwareJSONEncoder, ensure_ascii=False),
                        mimetype='application/json')

    # TODO : for test purpose, remove me
    from flask import request
    from . import test
    from ..xin import jsonify as xin_jsonify
    @bp.route('/hirefire/add')
    def add_route():
        x = int(request.args.get('x', 0))
        y = int(request.args.get('y', 0))
        test.add.delay(x, y)
        return 'wait for it...'

    @bp.route('/hirefire/add_results')
    def get_add_results_route():
        return xin_jsonify(_items=list(test.db['add'].find()))

    return bp