from flask import request, abort, current_app
from .tools import jsonify, parse_id


class Paginator:
    """Pagination heavy lifting"""
    def __init__(self):
        # Check request params
        try:
            self.max_results = int(request.args.get('max_results', 20))
            self.page = int(request.args.get('page', 1))
            self.skip = (self.page - 1) * self.max_results
            if self.skip < 0:
                abort(422, 'page params must be > 0')
            if self.max_results > 100:
                abort(422, 'max_results params must be < 100')
        except ValueError:
            abort(422, 'Invalid max_results and/or page params')
        bad_params = set(request.args.keys()) - {'page', 'max_results'}
        if bad_params:
            abort(422, 'Unknown params {}'.format(bad_params))

    def make_response(self, cursor):
        return jsonify({
            '_items': list(cursor),
            '_meta': {'max_results': self.max_results,
                      'total': cursor.count(with_limit_and_skip=False),
                      'page': self.page}
        })


def get_resource(resource, obj_id, auto_abort=True, projection=None):
    """Retrieve object from database with it ID and resource name"""
    obj_id = parse_id(obj_id)
    if not obj_id:
        if auto_abort:
            abort(422, 'invalid ObjectId `{}`'.format(obj_id))
        else:
            return None
    obj = current_app.data.db[resource].find_one({'_id': obj_id}, projection)
    if not obj:
        if auto_abort:
            abort(404, '`{}` is not a valid {} resource'.format(obj_id, resource))
        else:
            return None
    return obj


def get_payload():
    """Return the json payload if present or abort request"""
    payload = request.get_json()
    if not payload:
        abort(412, 'Content-Type is not `application/json`')
    return payload


def get_if_match():
    """Return the If-Match header if present or abort request"""
    if_match = request.headers.get('If-Match', None)
    if not if_match:
        abort(412, 'missing header If-Match')
    return if_match
