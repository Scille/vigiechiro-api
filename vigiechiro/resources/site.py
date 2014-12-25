from flask import current_app, abort, jsonify

from vigiechiro.xin import EveBlueprint
from .resource import relation, choice


STOC_SCHEMA = {
    'subdivision1': {'type': 'string', 'regex': r'^()$'},
    'subdivision2': {'type': 'string', 'regex': r'^()$'},
    'subdivision3': {'type': 'string', 'regex': r'^()$'},
    'subdivision4': {'type': 'string', 'regex': r'^()$'},
    'subdivision5': {'type': 'string', 'regex': r'^()$'},
    'subdivision6': {'type': 'string', 'regex': r'^()$'}
}


DOMAIN = {
    'item_title': 'site',
    'resource_methods': ['GET', 'POST'],
    'item_methods': ['GET', 'PATCH', 'PUT'],
    'schema': {
        'numero': {'type': 'integer', 'unique': True, 'readonly': True},
        'protocole': relation('protocoles', required=True),
        'commentaire': {'type': 'string'},
        'numero_grille_stoc': {'type': 'string'},
        'verrouille': {'type': 'boolean'},
        'coordonnee': {'type': 'point'},
        'url_cartographie': {'type': 'url'},
        'largeur': {'type': 'number'},
        'localite': {
            'type': 'list',
            'schema': {
                'coordonnee': {'type': 'point'},
                'representatif': {'type': 'boolean'},
                'habitat': {
                    'type': 'dict',
                    'schema': {
                        'date': {'type': 'datetime'},
                        'stoc_principal': {
                            'type': 'dict',
                            'schema': STOC_SCHEMA
                        },
                        'stoc_secondaire': {
                            'type': 'dict',
                            'schema': STOC_SCHEMA
                        }
                    }
                }
            }
        },
        'type_site': choice(['LINEAIRE', 'POLYGONE']),
        'generee_aleatoirement': {'type': 'boolean'},
        'justification_non_aleatoire': {'type': 'string'}
    }
}
sites = EveBlueprint('sites', __name__, domain=DOMAIN,
                     auto_prefix=True)


@sites.route('/stoc', methods=['GET'])
def display_stock():
    return jsonify(STOC_SCHEMA)


@sites.event
def on_insert(items):
    for item in items:
        # TODO use counter
        item['numero'] = 1
