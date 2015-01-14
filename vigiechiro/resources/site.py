"""
    Donnee site
    ~~~~~~~~~~~

    see: https://scille.atlassian.net/wiki/pages/viewpage.action?pageId=13893712
"""

from flask import current_app, abort, jsonify

from ..xin import EveBlueprint
from ..xin.domain import relation, choice


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
    'allowed_read_roles': ['Observateur'],
    'allowed_item_read_roles': ['Observateur'],
    'allowed_item_write_roles': ['Observateur'],
    'schema': {
        # 'numero': {'type': 'integer', 'unique': True, 'readonly': True},
        'protocole': relation('protocoles', required=True, writerights='Administrateur'),
        'observateur': relation('utilisateurs', writerights='Administrateur'),
        'commentaire': {'type': 'string'},
        'numero_grille_stoc': {'type': 'string'},
        'verrouille': {'type': 'boolean', 'writerights': 'Administrateur'},
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
    # TODO use counter
    pass
    # for item in items:
    #     item['numero'] = 1


def _check_rights(original):
    if current_app.g.request_user['role'] == 'Administrateur':
        return
    # Non-admin can only modify if the site is not already verrouille
    if original['verrouille']:
        abort(422, 'cannot modify the site once verrouille is set')


@sites.event
def on_update(updates, original):
    _check_rights(original)


@sites.event
def on_replace(item, original):
    _check_rights(original)
