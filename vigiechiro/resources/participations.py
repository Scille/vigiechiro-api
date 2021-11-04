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
                       ALLOWED_MIMES_TA, ALLOWED_MIMES_TC,
                       ALLOWED_MIMES_WAV, ALLOWED_MIMES_PROCESSING_EXTRA)
from .utilisateurs import utilisateurs as utilisateurs_resource, ensure_protocole_joined_and_validated
from .donnees import donnees as donnees_resource

from ..scripts import (process_participation, clean_deleted_participation,
                       email_observations_csv)


def _validate_site(context, site):
    print('validating site : {}'.format(fichier))
    if site['observateur'] != g.request_user['_id']:
        return "observateur doesn't own this site"
    if not site.get('verrouille', False):
        return "cannot create protocole on an unlocked site"


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
    'point': {'type': 'string'},
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
    'logs': relation('fichiers'),
    'traitement': {
        'type': 'dict',
        'schema': {
            'etat': choice(['PLANIFIE', 'EN_COURS', 'FINI', 'ERREUR', 'RETRY']),
            'retry': {'type': 'integer'},
            'date_planification': {'type': 'datetime'},
            'date_debut': {'type': 'datetime'},
            'date_fin': {'type': 'datetime'},
            'message': {'type': 'string'}
        }
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
    # Filter the result fields for perf...
    found = participations.find(get_lookup_from_q(), skip=pagination.skip,
        limit=pagination.max_results,
        projection={'protocole': False, 'messages': False,
                'logs': False, 'bilan': False})
    return pagination.make_response(*found)


@participations.route('/moi/participations', methods=['GET'])
@requires_auth(roles='Observateur')
def list_user_participations():
    pagination = Paginator()
    lookup = {'observateur': g.request_user['_id']}
    lookup.update(get_lookup_from_q() or {})
    found = participations.find(lookup, skip=pagination.skip,
        limit=pagination.max_results,
        projection={'observateur': False, 'protocole': False, 'messages': False,
                'logs': False, 'bilan': False})
    return pagination.make_response(*found)


@participations.route('/sites/<objectid:site_id>/participations', methods=['GET'])
@requires_auth(roles='Observateur')
def list_site_participations(site_id):
    pagination = Paginator()
    lookup = {'site': site_id}
    lookup.update(get_lookup_from_q() or {})
    found = participations.find(lookup, skip=pagination.skip,
        limit=pagination.max_results,
        projection={'protocole': False, 'site': False,
                'messages': False, 'logs': False, 'bilan': False})
    return pagination.make_response(*found)


@participations.route('/participations/<objectid:participation_id>', methods=['GET'])
@requires_auth(roles='Observateur')
def display_participation(participation_id):
    document = participations.find_one(participation_id)
    return document


@participations.route('/participations/<objectid:participation_id>', methods=['DELETE'])
@requires_auth(roles='Administrateur')
def delete_participation(participation_id):
    res = participations.remove({'_id': participation_id})
    if res.deleted_count:
        clean_deleted_participation.delay(participation_id)
        return {}, 204
    else:
        abort(404)


@participations.route('/participations/<objectid:participation_id>/csv', methods=['POST'])
@requires_auth(roles='Observateur')
def participation_generate_csv(participation_id):
    p = participations.find_one(participation_id, projection={
        'protocole': False, 'messages': False, 'logs': False, 'bilan': False})
    site_name = p['site']['titre']
    _check_read_access(p)
    body = """Bonjour {name},

Voici le csv des observations de la participation réalisée le {p_date} sur le site {p_site}.

{domain}/#/participations/{p_id}

Cordialement,

Vigiechiro
""".format(name=g.request_user['pseudo'], p_site=site_name,
           p_date=p['date_debut'], p_id=participation_id,
           domain=current_app.config['FRONTEND_DOMAIN'])
    subject = """Observations de la participation du {p_date} sur le site {p_site}""".format(p_site=site_name, p_date=p['date_debut'])
    email_observations_csv.delay(participation_id, recipient=g.request_user['email'], subject=subject, body=body)
    return {}, 200


def _build_participation_notify_msg(participation):
    return """Bonjour {name},

La participation réalisée le {p_date} sur le site {p_site} vient d'être traitée.

{domain}/#/participations/{p_id}

Cordialement,

Vigiechiro
""".format(name=g.request_user['pseudo'], p_site=participation['site']['titre'],
    p_date=participation['date_debut'], p_id=participation['_id'],
    domain=current_app.config['FRONTEND_DOMAIN'])


@participations.route('/participations/<objectid:participation_id>/compute', methods=['POST'])
@requires_auth(roles='Observateur')
def participation_trigger_compute(participation_id):
    participation_resource = participations.find_one(participation_id,
        projection={'protocole': False,
                'messages': False, 'logs': False, 'bilan': False})
    _check_edit_access(participation_resource)
    traitement = participation_resource.get('traitement', {})
    status = traitement.get('etat')
    # Skip if date_debut is older than one day
    if status in ('EN_COURS', 'PLANIFIE'):
        date_debut = traitement.get('date_debut')
        date_planif = traitement.get('date_planification')
        now = datetime.utcnow()
        if ((date_debut and (now - date_debut.replace(tzinfo=None)).days < 1) or
                (date_planif and (now - date_planif.replace(tzinfo=None)).days < 1)):
            abort(400, {'etat': 'Already %s' % status})
    process_participation.delay(participation_id,
        publique=participation_resource['observateur'].get('donnees_publiques', False),
        notify_mail=g.request_user['email'],
        notify_msg=_build_participation_notify_msg(participation_resource))
    participations.update(participation_id,
        payload={'traitement': {'etat': 'PLANIFIE', 'date_planification': datetime.utcnow()}})
    return {}, 200


@participations.route('/sites/<objectid:site_id>/participations', methods=['POST'])
@requires_auth(roles='Observateur')
def create_participation(site_id):
    payload = get_payload({'date_debut': False, 'date_fin': False,
                           'commentaire': False, 'meteo': False,
                           'configuration': False, 'point': ''})
    payload['observateur'] = g.request_user['_id']
    payload['site'] = site_id
    # Other inputs sanity check
    site_resource = get_resource('sites', site_id, auto_abort=False)
    if not site_resource:
        abort(422, {'site': 'no site with this id'})
    protocole_id = site_resource['protocole']
    payload['protocole'] = protocole_id
    # Make sure observateur has joined protocole and is validated
    err = ensure_protocole_joined_and_validated(protocole_id)
    if err:
        abort(422, err)
    # Create the participation
    document = participations.insert(payload)
    # Finally create corresponding actuality
    create_actuality_nouvelle_participation(document)
    return document, 201


def _check_edit_access(participation_resource):
    # Only owner and admin can edit
    p_obs = participation_resource['observateur']
    if isinstance(p_obs, dict):
        p_obs = p_obs['_id']
    if g.request_user['role'] != 'Administrateur' and g.request_user['_id'] != p_obs:
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
                           'configuration': False, 'bilan': False,
                           'point': ''})
    document = participations.update(participation_id, payload)
    return document


@participations.route('/participations/<objectid:participation_id>/pieces_jointes', methods=['PUT'])
@requires_auth(roles='Observateur')
def add_pieces_jointes(participation_id):
    # Deprecated route: use `lien_participation` param with `/fichiers` route instead
    participation_resource = participations.find_one(participation_id,
        projection={'protocole': False, 'messages': False, 'logs': False, 'bilan': False})
    _check_edit_access(participation_resource)
    errors = {}
    pjs_ids_str = get_payload({'pieces_jointes': True})['pieces_jointes']
    pjs_ids = []
    for pj_id_str in pjs_ids_str:
        pj_id = parse_id(pj_id_str)
        if pj_id is None:
            errors[pj_id_str] = 'Invalid ObjectId'
            continue
        pjs_ids.append(pj_id)
    if errors:
        abort(422, {'pieces_jointes': errors})
    process_participation.delay(participation_id, pjs_ids,
        utilisateurs_resource.get_resource(
            participation_resource['observateur']['_id']).get(
                'donnees_publiques', False),
            notify_mail=g.request_user['email'],
            notify_msg=_build_participation_notify_msg(participation_resource))
    participations.update(participation_id,
        payload={'traitement': {'etat': 'PLANIFIE', 'date_planification': datetime.utcnow()}})
    return {}, 200


@participations.route('/participations/<objectid:participation_id>/pieces_jointes', methods=['GET'])
@requires_auth(roles='Observateur')
def get_pieces_jointes(participation_id):
    participation_resource = participations.find_one(participation_id)
    _check_read_access(participation_resource)
    pagination = Paginator()
    params = get_url_params({'ta': {'type': bool}, 'tc': {'type': bool},
                             'wav': {'type': bool}, 'photos': {'type': bool},
                             'processing_extra': {'type': bool}})
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
        elif rule == "processing_extra":
            mimes = ALLOWED_MIMES_PROCESSING_EXTRA
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
    found = fichiers_resource.find(lookup, skip=pagination.skip,
        limit=pagination.max_results,
        projection={'proprietaire': False, 'lien_participation': False,
                'lien_donnee': False, 'lien_protocole': False})
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
