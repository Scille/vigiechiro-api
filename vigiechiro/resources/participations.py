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
from .donnees import donnees as donnees_resource
from ..scripts import tadaridaD, tadaridaC, participation_pj_link_donnees


def _validate_site(context, site):
    print('validating site : {}'.format(fichier))
    if site['observateur'] != g.request_user['_id']:
        return "observateur doesn't own this site"
    if not site.get('verrouille', False):
        return "cannot create protocole on an unlocked site"


def _validate_piece_jointe(context, fichier):
    print('validating fichier : {}'.format(fichier))
    if fichier['mime'] not in ALLOWED_MIMES_PHOTOS:
        return 'bad mime type, should be of {}'.format(ALLOWED_MIMES_PHOTOS)
    if not fichier.get('disponible', False):
        return 'upload is not done'.format(pj_id)


SCHEMA = {
    'observateur': relation('utilisateurs', required=True),
    'protocole': relation('protocoles', required=True),
    'site': relation('sites', required=True, validator=_validate_site),
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
        'keyschema': {'type': 'string'}
    },
    'bilan': {
        'type': 'dict',
        'schema': {
            'problemes': {'type': 'integer'},
            'autre': {
                'type': 'list',
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'taxon': relation('taxons', required=True),
                        'nb_contact_min': {'type': 'integer', 'required': True},
                        'nb_contact_max': {'type': 'integer', 'required': True}
                    }
                }
            },
            'chiropteres': {
                'type': 'list',
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'taxon': relation('taxons', required=True),
                        'nb_contact_min': {'type': 'integer', 'required': True},
                        'nb_contact_max': {'type': 'integer', 'required': True}
                    }
                }
            },
            'orthopteres': {
                'type': 'list',
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'taxon': relation('taxons', required=True),
                        'nb_contact_min': {'type': 'integer', 'required': True},
                        'nb_contact_max': {'type': 'integer', 'required': True}
                    }
                }
            }
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
    payload = get_payload({'date_debut': False, 'date_fin': False,
                           'commentaire': False, 'meteo': False,
                           'configuration': False})
    payload['observateur'] = g.request_user['_id']
    payload['site'] = site_id
    # Other inputs sanity check
    site_resource = get_resource('sites', site_id, auto_abort=False)
    if not site_resource:
        abort(422, {'site': 'no site with this id'})
    if not site_resource.get('verrouille', False):
        abort(422, {'site': "cannot create protocole on an unlocked site"})
    protocole_id = site_resource['protocole']
    payload['protocole'] = protocole_id
    # Make sure observateur has joined protocole and is validated
    joined = next((p for p in g.request_user.get('protocoles', [])
                   if p['protocole'] == protocole_id), None)
    if not joined:
        abort(422, {'site': 'not registered to corresponding protocole'})
    # Create the participation
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
                           'configuration': False, 'bilan': False})
    document = participations.update(participation_id, payload)
    return document


@participations.route('/participations/<objectid:participation_id>/pieces_jointes', methods=['PUT'])
@requires_auth(roles='Observateur')
def add_pieces_jointes(participation_id):
    participation_resource = participations.get_resource(participation_id)
    _check_edit_access(participation_resource)
    to_link_participation = []
    to_link_donnees = {}
    async_process_tadaridaC = []
    async_process_tadaridaD = []
    def add_to_link_donnees(pj_data):
        basename = pj_data['titre'].rsplit('.', 1)[0]
        if basename not in to_link_donnees:
            to_link_donnees[basename] = []
        to_link_donnees[basename].append(pj_data['_id'])
    # delay_tasks = []
    errors = {}
    # For each pj, check existance, make sure it is not linked to something
    # else, link to the participation/donnee, create a new donnee if needed
    # and finally trigger tadarida async process if needed
    pjs_ids_str =  get_payload({'pieces_jointes': True})['pieces_jointes']
    pjs_ids = []
    for pj_id_str in pjs_ids_str:
        pj_id = parse_id(pj_id_str)
        if pj_id is not None:
            pjs_ids.append(pj_id)
    pjs = [pj for pj in current_app.data.db.fichiers.find({'_id': {'$in': pjs_ids}})]
    pjs_ids_str_found = {str(pj['_id']) for pj in pjs}
    for pj_id_str in pjs_ids_str:
        if pj_id_str not in pjs_ids_str_found:
            errors[pj_id_str] = 'invalid fichiers resource objectid'
    for pj_data in pjs:
        pj_id = pj_data['_id']
        for link in 'lien_donnee', 'lien_participation', 'lien_protocole':
            if link in pj_data:
                errors[str(pj_id)] = 'fichiers already linked (has a `{}` field)'.format(link)
                break
        if pj_data['mime'] in ALLOWED_MIMES_WAV:
            add_to_link_donnees(pj_data)
            # delay_tasks.append(lambda pj_id=pj_id: tadaridaD.delay(pj_id))
            async_process_tadaridaD.append(pj_id)
        elif pj_data['mime'] in ALLOWED_MIMES_TA:
            add_to_link_donnees(pj_data)
            # TadaridaC has a heavy bootstraping cost, hence we use batch
            # processing instead of per-file
            # delay_tasks.append(lambda pj_id=pj_id: tadaridaC.delay(pj_id))
            async_process_tadaridaC.append(pj_id)
            continue
        elif pj_data['mime'] in ALLOWED_MIMES_TC:
            add_to_link_donnees(pj_data)
        elif pj_data['mime'] not in ALLOWED_MIMES_PHOTOS:
            errors[pj_id] = 'fichier has invalid mime type'
        to_link_participation.append(pj_id)
    if errors:
        abort(422, {'pieces_jointes': errors})
    # If we are here, everything is ok, we can start altering the bdd
    if to_link_participation:
        current_app.data.db.fichiers.update({'_id': {'$in': to_link_participation}},
                                            {'$set': {'lien_participation': participation_id}},
                                            multi=True)
    if async_process_tadaridaC:
        current_app.data.db.fichiers.update({'_id': {'$in': async_process_tadaridaC}},
                                            {'$set': {'lien_participation': participation_id,
                                                      '_async_process': 'tadaridaC'}},
                                            multi=True)
    participation_pj_link_donnees.delay(participation_id,
        participation_resource['observateur'],
        utilisateurs_resource.get_resource(
            participation_resource['observateur']).get(
                'donnees_publiques', False),
        to_link_donnees, async_process_tadaridaD)
    return {}, 200


@participations.route('/participations/<objectid:participation_id>/pieces_jointes', methods=['GET'])
@requires_auth(roles='Observateur')
def get_pieces_jointes(participation_id):
    participation_resource = participations.find_one(participation_id)
    _check_read_access(participation_resource)
    pagination = Paginator()
    params = get_url_params({'ta': {'type': bool}, 'tc': {'type': bool},
                             'wav': {'type': bool}, 'photos': {'type': bool}})
    lookup = {'lien_participation': participation_id}
    lookup.update(get_lookup_from_q() or {})
    for rule, value in params.items():
        mimes = []
        if rule == 'ta':
            mimes = ALLOWED_MIMES_TA
        elif rule == 'tc':
            mimes = ALLOWED_MIMES_TC
        elif rule == 'wav':
            mimes = ALLOWED_MIMES_WAV
        else:
            mimes = ALLOWED_MIMES_PHOTOS
        if 'mime' not in lookup:
            lookup['mime'] = {}
        if value:
            if '$in' not in lookup['mime']:
                lookup['mime']['$in'] = []
            lookup['mime']['$in'] += mimes
        else:
            if '$in' not in lookup['mime']:
                lookup['mime']['$nin'] = []
            lookup['mime']['$in'] += mimes
    found = fichiers_resource.find(lookup,
                                   skip=pagination.skip,
                                   limit=pagination.max_results)
    return pagination.make_response(*found)


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
