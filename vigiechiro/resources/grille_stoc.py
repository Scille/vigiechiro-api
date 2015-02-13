"""
    Donnee grille_stoc
    ~~~~~~~~~~~~~~~~~~

    wsg84 centroide data of France & DOM/TOM
"""

from flask import request, current_app

from ..xin import Resource
from ..xin.tools import abort
from ..xin.auth import requires_auth
from ..xin.snippets import Paginator


# Indicative schema given we won't do any insert
SCHEMA = {
    'centre': {'type': 'point'},
    'numero': {'type': 'string'}
}


grille_stoc = Resource('grille_stoc', __name__, schema=SCHEMA)


@grille_stoc.route('/grille_stoc', methods=['GET'])
@requires_auth(roles='Observateur')
def get_grille_stoc():
    args_names = ['sw_lng', 'sw_lat', 'ne_lng', 'ne_lat']
    pagination = Paginator()
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
            '$geoWithin': {
                '$box': [
                    [float_args['sw_lng'], float_args['sw_lat']],
                    [float_args['ne_lng'], float_args['ne_lat']]
                ]
            }
        }
    }
    cursor = current_app.data.db[grille_stoc.name].find(lookup, limit=40)
    return pagination.make_response(cursor)
