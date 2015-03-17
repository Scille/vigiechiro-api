"""
    Donnee participation
    ~~~~~~~~~~~~~~~~~~~~

    see: https://scille.atlassian.net/wiki/pages/viewpage.action?pageId=13893657
"""

from flask import abort, current_app, g
from datetime import datetime

from ..xin import Resource
from ..xin.tools import abort, parse_id
from ..xin.auth import requires_auth
from ..xin.schema import relation, choice
from ..xin.snippets import (Paginator, get_payload, get_resource,
                            get_lookup_from_q, get_url_params)

from .actualites import create_actuality_nouvelle_participation
from .fichiers import (fichiers as fichiers_resource, ALLOWED_MIMES_PHOTOS,
                       ALLOWED_MIMES_TA, ALLOWED_MIMES_TC, ALLOWED_MIMES_WAV)
from .utilisateurs import utilisateurs as utilisateurs_resource

SCHEMA = {
    'observateur': relation('utilisateurs', required=True),
    'protocole': relation('protocoles', required=True),
    'site': relation('sites', required=True),
    'date_debut': {'type': 'datetime', 'required': True},
    'date_fin': {'type': 'datetime'},
    'meteo': {
        'type': 'dict',
        'schema': {
            'temperature_debut': {'type': 'integer'},
            'temperature_fin': {'type': 'integer'},
            'vent': choice(['NUL', 'FAIBLE', 'MOYEN', 'FORT']),
            'couverture': choice(['0-25', '25-50', '50-75', '75-100']),
        }
    },
    'commentaire': {'type': 'string'},
    'messages': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'auteur': relation('utilisateurs', required=True),
                'message': {'type': 'string', 'required': True},
                'date': {'type': 'datetime', 'required': True},
            }
        }
    },
    'configuration': {
        'type': 'dict',
        'schema': {
            'detecteur_enregistreur_numero_serie': {'type': 'string'},
            # TODO : create the custom_code type (dynamically
            # parametrized regex)
            # 'detecteur_enregistreur_type': {'type': 'custom_code'},
            'micro0_position': choice(['SOL', 'CANOPEE']),
            'micro0_numero_serie': {'type': 'string'},
            # 'micro0_type': {'type': 'custom_code'},
            'micro0_hauteur': {'type': 'integer'},
            'micro1_position': choice(['SOL', 'CANOPEE']),
            'micro1_numero_serie': {'type': 'string'},
            # 'micro1_type': {'type': 'custom_code'},
            'micro1_hauteur': {'type': 'integer'},
            # 'piste0_expansion': {'type': 'custom_code'},
            # 'piste1_expansion': {'type': 'custom_code'}
        }
    }
}


participations = Resource('participations', __name__, schema=SCHEMA)


@participations.route('/participations', methods=['GET'])
@requires_auth(roles='Observateur')
def list_participations():
    pagination = Paginator()
    found = participations.find(get_lookup_from_q(), skip=pagination.skip,
                                limit=pagination.max_results)
    return pagination.make_response(*found)


@participations.route('/moi/participations', methods=['GET'])
@requires_auth(roles='Observateur')
def list_user_participations():
    pagination = Paginator()
    lookup = {'observateur': g.request_user['_id']}
    lookup.update(get_lookup_from_q() or {})
    found = participations.find(lookup,
                                 skip=pagination.skip,
                                 limit=pagination.max_results)
    return pagination.make_response(*found)


@participations.route('/sites/<objectid:site_id>/participations', methods=['GET'])
@requires_auth(roles='Observateur')
def list_site_participations(site_id):
    pagination = Paginator()
    lookup = {'site': site_id}
    lookup.update(get_lookup_from_q() or {})
    found = participations.find(lookup, skip=pagination.skip, limit=pagination.max_results)
    return pagination.make_response(*found)


@participations.route('/participations/<objectid:participation_id>', methods=['GET'])
@requires_auth(roles='Observateur')
def display_participation(participation_id):
    document = participations.find_one(participation_id)
    return document


@participations.route('/sites/<objectid:site_id>/participations', methods=['POST'])
@requires_auth(roles='Observateur')
def create_participation(site_id):
    # TODO : handle numero automatically
    # payload = get_payload({'numero': True, 'date_debut': False,
    payload = get_payload({'date_debut': False, 'date_fin': False,
                           'commentaire': False, 'meteo': False,
                           'configuration': False})
    payload['observateur'] = g.request_user['_id']
    payload['site'] = site_id
    site_resource = get_resource('sites', site_id, auto_abort=False)
    if not site_resource:
        abort(422, {'site': 'no site with this id'})
    if site_resource['observateur'] != g.request_user['_id']:
        abort(422, {'site': "observateur doesn't own this site"})
    if not site_resource.get('verrouille', False):
        abort(422, {'site': "cannot create protocole on an unlocked site"})
    protocole_id = site_resource['protocole']
    payload['protocole'] = protocole_id
    # Make sure observateur has joined protocole and is validated
    joined = next((p for p in g.request_user.get('protocoles', [])
                   if p['protocole'] == protocole_id), None)
    if not joined:
        abort(422, {'site': 'not registered to corresponding protocole'})
    document = participations.insert(payload)
    # Finally create corresponding actuality
    create_actuality_nouvelle_participation(document)
    return document, 201


def _check_edit_access(participation_resource):
    # Only owner and admin can edit
    if (g.request_user['role'] != 'Administrateur' and
        g.request_user['_id'] != participation_resource['observateur']):
        abort(403)


def _check_read_access(participation_resource):
    owner = participation_resource['observateur']
    # If donnees_publiques, anyone can see
    # If not, only admin, validateur and owner can
    if (g.request_user['role'] == 'Administrateur' or
        g.request_user['role'] == 'Validateur' or
        g.request_user['_id'] == owner['_id']):
        return
    if not owner.get('donnees_publiques', False):
        abort(403)


def _check_add_message_access(participation_resource):
    # Administrateur, Validateur and owner are allowed
    if (g.request_user['role'] == 'Observateur' and
        g.request_user['_id'] != participation_resource['observateur']):
        abort(403)


@participations.route('/participations/<objectid:participation_id>', methods=['PATCH'])
@requires_auth(roles='Observateur')
def edit_participation(participation_id):
    participation_resource = participations.get_resource(participation_id)
    _check_edit_access(participation_resource)
    payload = get_payload({'date_debut': False, 'date_fin': False,
                           'commentaire': False, 'meteo': False,
                           'configuration': False})
    document = participations.update(participation_id, payload)
    return document


@participations.route('/participations/<objectid:participation_id>/pieces_jointes', methods=['PUT'])
@requires_auth(roles='Observateur')
def add_pieces_jointes(participation_id):
    participation_resource = participations.get_resource(participation_id)
    _check_edit_access(participation_resource)
    payload = get_payload({'photos', 'ta', 'wav'})
    errors = {}
    for field in ['ta', 'wav', 'photos']:
        if not isinstance(payload.get(field, []), list):
            errors[field] = 'must be a list'
    if errors:
        abort(422, errors)
    def check_pj(pj_id, mime):
        mime = mime if isinstance(mime, list) else [mime]
        pj = fichiers_resource.get_resource(pj_id, auto_abort=False)
        if not pj:
            return 'bad id {}'.format(pj_id), pj
        elif pj['mime'] not in mime:
            return 'file {} bad mime type, should be of {}'.format(pj_id, mime), pj
        elif not pj.get('disponible', False):
            return 'file {} upload is not done'.format(pj_id), pj
        return None, pj
    errors_photos = []
    errors_ta = []
    errors_wav = []
    photos_ids = [parse_id(_id) for _id in payload.get('photos', [])]
    ta_ids = [parse_id(_id) for _id in payload.get('ta', [])]
    wav_ids = [parse_id(_id) for _id in payload.get('wav', [])]
    if next((_id for _id in photos_ids+ta_ids+wav_ids if _id == None), None):
        abort(422, 'some given ids are not valid ObjectId')
    if not photos_ids and not ta_ids and not wav_ids:
        abort(422, 'at least one field among ta, wav and photos is required')
    for pj_id in photos_ids:
        error, pj = check_pj(pj_id, ALLOWED_MIMES_PHOTOS)
        if error:
            errors_photos.append(error)
    for pj_id in ta_ids:
        error, pj = check_pj(pj_id, ALLOWED_MIMES_TA)
        if error:
            errors_ta.append(error)
    for pj_id in wav_ids:
        error, pj = check_pj(pj_id, ALLOWED_MIMES_WAV)
        if error:
            errors_wav.append(error)
    if errors_wav or errors_ta or errors_photos:
        abort(422, {'photos': errors_photos, 'ta': errors_ta, 'wav': errors_wav})
    # The pieces jointes are valid, update the database
    result = {}
    if wav_ids:
        result['wav'] = current_app.data.db.fichiers.update(
            {'_id': {'$in': wav_ids}},
            {'$set': {
                'require_process': 'tadarida_d',
                'lien_participation': participation_id}
            }, multi=True)
    if ta_ids:
        result['ta'] = current_app.data.db.fichiers.update(
            {'_id': {'$in': ta_ids}},
            {'$set': {
                'require_process': 'tadarida_c',
                'lien_participation': participation_id}
            }, multi=True)
    if photos_ids:
        result['photos'] = current_app.data.db.fichiers.update(
            {'_id': {'$in': photos_ids}},
            {'$set': {'lien_participation': participation_id}},
            multi=True)
    return result


@participations.route('/participations/<objectid:participation_id>/pieces_jointes', methods=['GET'])
@requires_auth(roles='Observateur')
def get_pieces_jointes(participation_id):
    # import pdb; pdb.set_trace()
    params = get_url_params({
        'photos': {'required': False, 'type': bool},
        'ta': {'required': False, 'type': bool},
        'tc': {'required': False, 'type': bool},
        'wav': {'required': False, 'type': bool}
    })
    participation_resource = participations.find_one(participation_id)
    _check_read_access(participation_resource)
    lookup = {'lien_participation': participation_resource['_id']}
    if params:
        allowed_mimes = []
        result = {}
        if params.get('photos', False):
            allowed_mimes += ALLOWED_MIMES_PHOTOS
            result['photos'] = []
        if params.get('ta', False):
            allowed_mimes += ALLOWED_MIMES_TA
            result['ta'] = []
        if params.get('tc', False):
            allowed_mimes += ALLOWED_MIMES_TC
            result['tc'] = []
        if params.get('wav', False):
            allowed_mimes += ALLOWED_MIMES_WAV
            result['wav'] = []
        lookup['mime'] = {'$in': allowed_mimes}
    else:
        result = {'photos': [], 'ta': [], 'tc': [], 'wav': []}
    pieces_jointes = current_app.data.db.fichiers.find(lookup)
    for pj in pieces_jointes:
        if pj['mime'] in ALLOWED_MIMES_PHOTOS:
            result['photos'].append(pj)
        elif pj['mime'] in ALLOWED_MIMES_TA:
            result['ta'].append(pj)
        elif pj['mime'] in ALLOWED_MIMES_TC:
            result['tc'].append(pj)
        elif pj['mime'] in ALLOWED_MIMES_WAV:
            result['wav'].append(pj)
    return result


@participations.route('/participations/<objectid:participation_id>/messages', methods=['PUT'])
@requires_auth(roles='Observateur')
def add_post(participation_id):
    participation_resource = participations.get_resource(participation_id)
    _check_add_message_access(participation_resource)
    new_message = {'auteur': g.request_user['_id'], 'date': datetime.utcnow(),
                   'message': get_payload({'message': True})['message']}
    payload = {'messages': [new_message]}
    mongo_update = {'$push': {'messages': {
                        '$each': payload['messages'],
                        '$position': 0
                    }}}
    return participations.update(participation_id, payload=payload,
                                 mongo_update=mongo_update)
