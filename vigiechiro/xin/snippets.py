from flask import request, abort, current_app, g
from pymongo.cursor import Cursor
import json

from .tools import jsonify, parse_id


class Paginator:
    """Pagination heavy lifting"""
    def __init__(self, max_results_limit=100, args=None):
        args = args if args else request.args
        # Check request params
        try:
            self.max_results = int(args.get('max_results', 20))
            self.page = int(args.get('page', 1))
            self.skip = (self.page - 1) * self.max_results
            if self.skip < 0:
                abort(422, 'page params must be > 0')
            if self.max_results > max_results_limit:
                abort(422, 'max_results params must be < {}'.format(
                    max_results_limit))
        except ValueError:
            abort(422, 'Invalid max_results and/or page params')

    def make_response(self, items, total=None):
        if isinstance(items, Cursor):
            total = items.count(with_limit_and_skip=False)
            items = list(items)
        return jsonify({
            '_items': items,
            '_meta': {'max_results': self.max_results,
                      'total': total,
                      'page': self.page}
        })


def get_resource(resource, obj_id, field='_id', auto_abort=True, projection=None):
    """Retrieve object from database with it ID and resource name"""
    obj_id = parse_id(obj_id)
    if not obj_id:
        if auto_abort:
            abort(422, 'invalid ObjectId `{}`'.format(obj_id))
        else:
            return None
    cache = getattr(g, '_cache_get_resource', None)
    if not cache:
        g._cache_get_resource = {}
    key = (resource, obj_id, field, json.dumps(projection))
    obj = g._cache_get_resource.get(key)
    if not obj:
        obj = current_app.data.db[resource].find_one({field: obj_id}, projection)
        if not obj:
            if auto_abort:
                abort(404, '`{}` is not a valid {} resource'.format(obj_id, resource))
            else:
                return None
        g._cache_get_resource[key] = obj
    return obj


def get_payload(allowed_fields=None):
    """Return the json payload if present or abort request"""
    payload = request.get_json()
    if not isinstance(payload, dict):
        abort(412, 'Content-Type is not `application/json`')
    provided_fields = set(payload.keys())
    if allowed_fields:
        invalid_fields = provided_fields - set(allowed_fields)
        if invalid_fields:
            abort(422, {field: 'invalid field' for field in invalid_fields})
    if isinstance(allowed_fields, dict):
        mandatory_fields = {f for f, v in allowed_fields.items() if v}
        missing_fields = mandatory_fields - provided_fields
        if missing_fields:
            abort(422, {field: 'missing field' for field in missing_fields})
    return payload


def get_url_params(params_spec=None, args=None):
    """
        Retrieve the given params in url or abort request
        :param params_spec: list of required arguments or dict of params/config
        :param args: request.args by default
        (i.g. `{'a': {'required': True, 'type': int}, 'b': {}}`)
    """
    args = args if args else request.args
    if not params_spec:
        return
    result = {}
    errors = {}
    if isinstance(params_spec, list):
        params_spec = {a: {} for a in params_spec}
    for param, config in params_spec.items():
        if isinstance(config, bool):
            config = {'required': config}
        if param not in args:
            if config.get('required', False):
                errors[param] = 'missing required param'
            continue
        param_type = config.get('type', str)
        try:
            if param_type is bool:
                if args[param].lower() == 'true':
                    result[param] = True
                elif args[param].lower() == 'false':
                    result[param] = False
                else:
                    raise ValueError()
            else:
                result[param] = param_type(args[param])
        except:
            errors[param] = 'bad value, should be {}'.format(param_type)
    if errors:
        abort(422, errors)
    return result


def get_if_match():
    """Return the If-Match header if present or abort request"""
    if_match = request.headers.get('If-Match', None)
    if not if_match:
        abort(412, 'missing header If-Match')
    return if_match


def get_lookup_from_q(params=None):
    """Create a mongodb lookup dict from q param present in url's arguments"""
    params = params if params else request.args
    if 'q' in params:
        return {'$text': {'$search': params['q']}}
    else:
        return None
