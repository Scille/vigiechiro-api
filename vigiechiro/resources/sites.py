"""
    Donnee site
    ~~~~~~~~~~~

    see: https://scille.atlassian.net/wiki/pages/viewpage.action?pageId=13893712
"""

from flask import current_app, abort, jsonify, g
from datetime import datetime

from ..xin import Resource
from ..xin.tools import jsonify, abort
from ..xin.auth import requires_auth
from ..xin.schema import relation, choice
from ..xin.snippets import get_payload, get_if_match, Paginator, get_resource

from .actualites import create_actuality_nouveau_site
from .protocoles import check_configuration_participation

STOC_SCHEMA = {
    'subdivision1': {'type': 'string', 'regex': r'^()$'},
    'subdivision2': {'type': 'string', 'regex': r'^()$'},
    'subdivision3': {'type': 'string', 'regex': r'^()$'},
    'subdivision4': {'type': 'string', 'regex': r'^()$'},
    'subdivision5': {'type': 'string', 'regex': r'^()$'},
    'subdivision6': {'type': 'string', 'regex': r'^()$'}
}


SCHEMA = {
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
                'nom': {'type': 'string', 'required': True},
                'coordonnee': {'type': 'point'},
                'geometries': {'type': 'geometrycollection'},
                'representatif': {'type': 'boolean'},
                'habitats': {
                    'type': 'list',
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'date': {'type': 'datetime', 'required': True},
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


sites = Resource('sites', __name__, schema=SCHEMA)


@sites.route('/sites', methods=['GET'])
@requires_auth(roles='Observateur')
def list_sites():
    pagination = Paginator()
    cursor = sites.find(skip=pagination.skip, limit=pagination.max_results)
    return pagination.make_response(cursor)


@sites.route('/sites', methods=['POST'])
@requires_auth(roles='Observateur')
def create_site():
    payload = get_payload({'protocole', 'commentaire', 'grille_stoc'})
    payload['observateur'] = g.request_user['_id']
    protocole_resource = get_resource('protocoles',
        payload.get('protocole', None), auto_abort=False)
    if not protocole_resource:
        abort(422, {'protocole': 'invalid or missing field'})
    # TODO select type_site according to protocole
    protocole_id = protocole_resource['_id']
    # Make sure observateur has joined protocole and is validated
    joined = next((p for p in g.request_user.get('protocoles', [])
                   if p['protocole'] == protocole_id), None)
    if not joined:
        abort(422, 'not registered to protocole')
    if joined.get('verrouille', False):
        abort(422, 'protocole must be validate before creating site')
    inserted_payload = sites.insert(payload)
    # Finally create corresponding actuality
    create_actuality_nouveau_site(inserted_payload)
    return jsonify(**inserted_payload), 201


@sites.route('/sites/<objectid:site_id>', methods=['GET'])
@requires_auth(roles='Observateur')
def display_site(site_id):
    return jsonify(**sites.get_resource(site_id))


@sites.route('/sites/<objectid:site_id>/verrouille', methods=['PATCH'])
@requires_auth(roles='Administrateur')
def lock_site(site_id):
    payload = get_payload({'verrouille'})
    if 'verrouille' not in payload:
        abort(422, {'verrouille': 'missing field'})
    return jsonify(**sites.update(site_id, {'verrouille': payload['verrouille']}))


def _check_edit_acess(site_resource):
    """Access policy : administrateur or owner if site is not yet verrouille"""
    is_owner = site_resource['observateur'] == g.request_user['_id']
    if (g.request_user['role'] != 'Administrateur' and
        (not is_owner or site_resource.get('verrouille', False))):
        abort(403)


@sites.route('/sites/<objectid:site_id>', methods=['PATCH'])
@requires_auth(roles='Observateur')
def edit_site(site_id):
    site_resource = sites.get_resource(site_id)
    _check_edit_acess(site_resource)
    payload = get_payload({'commentaire', 'grille_stoc'})
    check_configuration_participation(payload)
    result = sites.update(site_id, payload, get_if_match())
    return jsonify(**result)


@sites.route('/sites/<objectid:site_id>/observateur', methods=['PATCH'])
@requires_auth(roles='Administrateur')
def change_observateur_site(site_id):
    payload = get_payload({'observateur': True})
    site_resource = sites.get_resource(site_id)
    result = sites.update(site_id, payload)
    return jsonify(**result)


@sites.route('/sites/liste', methods=['GET'])
@requires_auth(roles='Observateur')
def get_resume_list():
    """Return a brief list of per site id and libelle"""
    items = sites.find({}, {"libelle_long": 1})
    return jsonify(_items=[i for i in items])


@sites.route('/sites/<objectid:site_id>/localite', methods=['PUT'])
@requires_auth(roles='Observateur')
def add_localite(site_id):
    site_resource = sites.get_resource(site_id)
    _check_edit_acess(site_resource)
    payload = get_payload({'nom', 'coordonnee', 'geometries', 'representatif'})
    # Make sure given nom is unique
    nom = payload.get('nom', None)
    if not nom:
        abort(422, {'nom': 'required field'})
    localites = site_resource.get('localites', [])
    existing_nom = next((l for l in localites if l['nom'] == nom), None)
    if existing_nom:
        abort(422, {'nom': 'another localite has already this name'})
    localites.append(payload)
    result = sites.update(site_id, localites)
    return jsonify(**result)


@sites.route('/sites/<objectid:site_id>/localite/<localite_nom>/habitat', methods=['PUT'])
@requires_auth(roles='Observateur')
def add_site_habitat(site_id):
    site_resource = sites.get_resource(site_id)
    # Retrieve the localite
    localites = site_resource.get('localites', [])
    localite = next((l for l in localites if l['nom'] == nom), None)
    if not localite:
        abort(422, "localite `{}` doesn't exist".format())
    payload = get_payload({'stoc_principal', 'stoc_secondaire'})
    payload['date'] = datetime.utcnow()
    habitats = localite.get('habitats', [])
    habitats.append(payload)
    check_configuration_participation(payload)
    result = sites.update(site_id, {'localites': localites})
    return jsonify(**result)
