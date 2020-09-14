"""
    Donnee site
    ~~~~~~~~~~~

    see: https://scille.atlassian.net/wiki/pages/viewpage.action?pageId=13893712
"""

from flask import current_app, abort, jsonify, g, request
from datetime import datetime
from bson import ObjectId
import logging

from ..xin import Resource
from ..xin.tools import jsonify, abort, parse_id
from ..xin.auth import requires_auth
from ..xin.schema import relation, choice
from ..xin.snippets import Paginator, get_payload, get_resource, get_url_params

from .actualites import create_actuality_nouveau_site, create_actuality_verrouille_site
from .protocoles import check_configuration_participation
from .grille_stoc import grille_stoc
from .utilisateurs import ensure_protocole_joined_and_validated
from ..scripts import clean_deleted_site


STOC_SCHEMA = {
    'subdivision1': {'type': 'string', 'regex': r'^()$'},
    'subdivision2': {'type': 'string', 'regex': r'^()$'},
    'subdivision3': {'type': 'string', 'regex': r'^()$'},
    'subdivision4': {'type': 'string', 'regex': r'^()$'},
    'subdivision5': {'type': 'string', 'regex': r'^()$'},
    'subdivision6': {'type': 'string', 'regex': r'^()$'}
}


SCHEMA = {
    'titre': {'type': 'string', 'required': True, 'unique': True, 'postonly': True},
    'protocole': relation('protocoles', required=True, postonly=True),
    'observateur': relation('utilisateurs', postonly=True),
    'commentaire': {'type': 'string'},
    'grille_stoc': relation('grille_stoc', postonly=True),
    'verrouille': {'type': 'boolean'},
    'tracet': {
        'type': 'dict',
        'schema': {
            'chemin': {'type': 'linestring'},
            'origine': {'type': 'point'},
            'arrivee': {'type': 'point'}
        }
    },
    'url_cartographie': {'type': 'url'},
    'largeur': {'type': 'number'},
    'localites': {
        'type': 'list',
        'unique_field': 'nom',
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


@sites.validator.attribute
def unique_field(context):
    path = context.get_current_path()
    # node = context.additional_context.get('old_document', {})
    # for field in path.split('.'):
    #     if field in node:
    #         node = node[field]
    #     else:
    #         node = None
    #         break
    # old_field_value = node or []
    field = context.schema['unique_field']
    field_values = []
    # for elem in context.value + old_field_value:
    for elem in context.value:
        if field in elem:
            field_values.append(elem[field])
    if len(field_values) != len(set(field_values)):
        context.add_error("field {} has duplicated values".format(field))


def _sites_generic_list(params):
    # Make sure no bad params provided
    params = get_url_params({'q': {'type': str},
                             'protocole': {'type': ObjectId},
                             'observateur': {'type': ObjectId},
                             'grille_stoc': {'type': ObjectId},
                             'max_results': {'type': int},
                             'page': {'type': int}},
                            args=params)
    lookup = {}
    if 'q' in params:
        lookup['$text'] = {'$search': params['q']}
    for field in ['protocole', 'observateur', 'grille_stoc']:
        if field in params:
            lookup[field] = params[field]
    pagination = Paginator(args=params)
    found = sites.find(lookup or None, sort=[('titre', 1)], skip=pagination.skip,
                       limit=pagination.max_results)
    return pagination.make_response(*found)


@sites.route('/sites', methods=['GET'])
@requires_auth(roles='Observateur')
def list_sites():
    return _sites_generic_list(request.args)


@sites.route('/moi/sites', methods=['GET'])
@requires_auth(roles='Observateur')
def list_user_sites():
    params = request.args.copy()
    params['observateur'] = g.request_user['_id']
    return _sites_generic_list(params)


@sites.route('/protocoles/<objectid:protocole_id>/sites', methods=['GET'])
@requires_auth(roles='Observateur')
def list_protocole_sites(protocole_id):
    params = request.args.copy()
    params['protocole'] = protocole_id
    return _sites_generic_list(params)


@sites.route('/protocoles/<objectid:protocole_id>/sites/grille_stoc', methods=['GET'])
@requires_auth(roles='Observateur')
def list_protocole_sites_grille_stoc(protocole_id):
    """Return a list of sites with grille_stoc for a protocol"""
    pagination = Paginator(max_results_limit=2000)
    protocoles = current_app.data.db[sites.name].find(
        {'protocole': protocole_id}, {'grille_stoc': 1},
        skip=pagination.skip, limit=pagination.max_results)
    # Fetch all grilles stoc in one query to improve perfs
    total = protocoles.count(with_limit_and_skip=False)
    protocoles = list(protocoles)
    grille_ids = [x['grille_stoc'] for x in protocoles]
    grilles_per_id = {x['_id']: x for x in grille_stoc.find({'_id': {'$in': grille_ids}})[0]}
    for item in protocoles:
        item['grille_stoc'] = grilles_per_id[item['grille_stoc']]
    return pagination.make_response(protocoles, total=total)


@sites.route('/protocoles/<objectid:protocole_id>/sites/tracet', methods=['GET'])
@requires_auth(roles='Observateur')
def list_protocole_sites_tracet(protocole_id):
    """Return a list of sites with tracet for a protocol"""
    pagination = Paginator(max_results_limit=2000)
    found = sites.find({"protocole": protocole_id}, {"tracet": 1},
                       skip=pagination.skip, limit=pagination.max_results)
    return pagination.make_response(*found)


@sites.route('/sites', methods=['POST'])
@requires_auth(roles='Observateur')
def create_site():
    payload = get_payload({
        'titre',
        'protocole',
        'commentaire',
        'grille_stoc',
        'tracet',
        'justification_non_aleatoire',
        'generee_aleatoirement'})
    payload['observateur'] = g.request_user['_id']
    # Get protocole resource
    protocole_resource = get_resource('protocoles',
        payload.get('protocole', None), auto_abort=False)
    if not protocole_resource:
        abort(422, {'protocole': 'invalid or missing field'})
    # Make sure observateur has joined protocole and is validated
    err = ensure_protocole_joined_and_validated(protocole_resource['_id'])
    if err:
        abort(422, err)
    # Get grille stoc resource
    grille_stoc_resource = get_resource('grille_stoc',
        payload.get('grille_stoc', None), auto_abort=False)
    # Create site title
    type_site = protocole_resource['type_site']
    if 'titre' in payload:
        pass
    elif type_site in ['CARRE', 'POINT_FIXE']:
        if not grille_stoc_resource:
            abort(422, 'site from protocole CARRE and POINT_FIXE '
                       'must provide a valid grille_stoc field')
        payload['titre'] = "{}-{}".format(protocole_resource['titre'],
                                          grille_stoc_resource['numero'])
    elif type_site == 'ROUTIER':
        routier_count = current_app.data.db.configuration.find_and_modify(
            query={'name': 'increments'},
            update={'$inc': {'protocole_routier_count': 1}}, new=True)
        if not routier_count:
            raise RuntimeError('Cannot increment `protocole_routier_count`, is '
                               '`configuration` collection containing an '
                               '`increments` document ?')
        payload['titre'] = "{}-{}".format(protocole_resource['titre'],
                                          routier_count['protocole_routier_count'])
    inserted_payload = sites.insert(payload)
    # Finally create corresponding actuality
    create_actuality_nouveau_site(inserted_payload['_id'],
                                  inserted_payload['observateur'],
                                  inserted_payload['protocole'])
    return inserted_payload, 201


@sites.route('/sites/<objectid:site_id>', methods=['GET'])
@requires_auth(roles='Observateur')
def display_site(site_id):
    return sites.find_one({'_id': site_id})


@sites.route('/sites/<objectid:site_id>', methods=['DELETE'])
@requires_auth(roles='Administrateur')
def delete_site(site_id):
    res = sites.remove({'_id': site_id})
    if res.deleted_count:
        clean_deleted_site.delay(site_id)
        return {}, 204
    else:
        abort(404)


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
    payload = get_payload({'commentaire', 'observateur', 'verrouille', 'tracet', 'titre'})
    if (('observateur' in payload or 'verrouille' in payload or 'titre' in payload)
        and g.request_user['role'] != 'Administrateur'):
        abort(403)
    check_configuration_participation(payload)
    result = sites.update(site_id, payload)
    if payload.get('verrouille', None) == True:
        create_actuality_verrouille_site(site_id, site_resource['observateur'])
    return result


@sites.route('/sites/liste', methods=['GET'])
@requires_auth(roles='Observateur')
def get_resume_list():
    """Return a brief list of per site id and libelle"""
    items = sites.find({}, {"libelle_long": 1})
    return {'_items': [i for i in items]}


@sites.route('/sites/<objectid:site_id>/localites', methods=['PUT'])
@requires_auth(roles='Observateur')
def set_localite(site_id):
    payload = get_payload({'localites': True})
    site_resource = sites.get_resource(site_id)
    is_owner = site_resource['observateur'] == g.request_user['_id']
    if g.request_user['role'] != 'Administrateur':
        if is_owner and site_resource.get('verrouille', False):
            abort(403)
        elif not is_owner:
            valid = False
            for protocole in g.request_user['protocoles'] or []:
                if protocole['protocole'] == site_resource['protocole']:
                    if protocole['valide']:
                        valid = True
                    break
            if not valid:
                abort(403)
    mongo_update = {'$set': {'localites': payload['localites']}}
    result = sites.update(site_id, payload=payload, mongo_update=mongo_update)
    return result


@sites.route('/sites/<objectid:site_id>/localites/<localite_nom>/habitat', methods=['PUT'])
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
    return result
