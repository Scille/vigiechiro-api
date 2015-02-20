from flask import request, abort, current_app
from pymongo.cursor import Cursor

from .tools import jsonify, parse_id


class Paginator:
    """Pagination heavy lifting"""
    def __init__(self, max_results_limit=20):
        # Check request params
        try:
            self.max_results = int(request.args.get('max_results', 20))
            self.page = int(request.args.get('page', 1))
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
    obj = current_app.data.db[resource].find_one({field: obj_id}, projection)
    if not obj:
        if auto_abort:
            abort(404, '`{}` is not a valid {} resource'.format(obj_id, resource))
        else:
            return None
    return obj


def get_payload(allowed_fields=None):
    """Return the json payload if present or abort request"""
    payload = request.get_json()
    if not payload:
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


def get_url_params(params=None):
    """
        Retrieve the given params in url or abort request
        :param params: list of required arguments or dict of params/config
        (i.g. `{'a': {'required': True, 'type': int}, 'b': {}}`)
    """
    if not params:
        return
    result = {}
    errors = {}
    if isinstance(params, list):
        params = {a: {} for a in params}
    for param, config in params.items():
        if config.get('required', False) and param not in request.args:
            errors[param] = 'missing required param'
            continue
        param_type = config.get('type', str)
        try:
            result[param] = param_type(request.args[param])
        except ValueError:
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
