"""
    Donnee site
    ~~~~~~~~~~~

    see: https://scille.atlassian.net/wiki/pages/viewpage.action?pageId=13893712
"""

from flask import current_app, abort, jsonify

from ..xin import EveBlueprint
from ..xin.domain import relation, choice, get_resource

from . import actualite


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
    'allowed_write_roles': ['Observateur'],
    'allowed_item_read_roles': ['Observateur'],
    'allowed_item_write_roles': ['Observateur'],
    'schema': {
        # 'numero': {'type': 'integer', 'unique': True, 'readonly': True},
        'protocole': relation('protocoles', required=True, postonly=True),
        'observateur': relation('utilisateurs', postonly=True),
        'commentaire': {'type': 'string'},
        'grille_stoc': relation('grille_stoc', embeddable=True),
        'verrouille': {'type': 'boolean', 'writerights': 'Administrateur'},
        'coordonnee': {'type': 'point'},
        'url_cartographie': {'type': 'url'},
        'largeur': {'type': 'number'},
        'localites': {
            'type': 'list',
            'schema': {
                'type': 'dict',
                'schema': {
                    'coordonnee': {'type': 'point'},
                    'geometries': {'type': 'geometrycollection'},
                    'representatif': {'type': 'boolean'},
                    'habitats': {
                        'type': 'list',
                        'schema': {
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
        # observateur field can be explicitely set by admin,
        # otherwise it is set to the request user
        request_user = current_app.g.request_user
        if 'observateur' not in item:
            item['observateur'] = request_user['_id']
        if (request_user['role'] != 'Administrateur' and
            item['observateur'] != request_user['_id']):
            abort(422, 'Observateur cannot specify site owner')
        # Make sure the observateur is part of the site's protocole
        observateur = get_resource('utilisateurs', item['observateur'])
        if not next((p for p in observateur.get('protocoles', [])
                     if p['protocole'] == item['protocole']), None):
            abort(422, 'Cannot create site without subscribing to protocole')


@sites.event
def on_inserted(items):
    for item in items:
        actualite.create_actuality('NOUVEAU_SITE',
            sujet=current_app.g.request_user['_id'], objet=item['_id'])


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
