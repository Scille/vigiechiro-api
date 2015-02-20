"""
    Donnee grille_stoc
    ~~~~~~~~~~~~~~~~~~

    wsg84 centroide data of France & DOM/TOM
"""

from flask import request, current_app

from ..xin import Resource
from ..xin.tools import jsonify, abort
from ..xin.auth import requires_auth
from ..xin.snippets import Paginator, get_url_params


# Indicative schema given we won't do any insert
SCHEMA = {
    'centre': {'type': 'point'},
    'numero': {'type': 'string'}
}


grille_stoc = Resource('grille_stoc', __name__, schema=SCHEMA)


@grille_stoc.route('/grille_stoc/rectangle', methods=['GET'])
@requires_auth(roles='Observateur')
def get_grille_stoc():
    params = get_url_params({
        'sw_lng': {'required': True, 'type': float},
        'sw_lat': {'required': True, 'type': float},
        'ne_lng': {'required': True, 'type': float},
        'ne_lat': {'required': True, 'type': float}
    })
    pagination = Paginator()
    lookup = {
        'centre': {
            '$geoWithin': {
                '$box': [
                    [params['sw_lng'], params['sw_lat']],
                    [params['ne_lng'], params['ne_lat']]
                ]
            }
        }
    }
    cursor = current_app.data.db[grille_stoc.name].find(lookup, limit=40)
    return pagination.make_response(cursor)


@grille_stoc.route('/grille_stoc/proximite', methods=['GET'])
@requires_auth(roles='Observateur')
def get_nearest_grille_stoc():
    args_names = ['lng', 'lat']
    missing = [arg for arg in args_names if arg not in request.args]
    if missing:
        abort(422, {f: 'missing param' for f in missing})
    float_args = {}
    errors = {}
    for arg in args_names:
        if arg not in request.args:
            errors[arg] = 'missing param'
        else:
            try:
                float_args[arg] = float(request.args[arg])
            except ValueError:
                errors[arg] = 'bad value, should be float'
    if errors:
        abort(422, errors)
    lookup = {
        'centre': {
            '$near': {
                '$geometry': {
                    'type': "Point",
                    'coordinates': [float_args['lng'], float_args['lat']]
                },
                '$maxDistance': 3000
            }
        }
    }
    obj = current_app.data.db[grille_stoc.name].find_one(lookup)
    return jsonify(**obj)
