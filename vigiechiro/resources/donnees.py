"""
    Donnee resource
    ~~~~~~~~~~~~~~~

    see: https://scille.atlassian.net/wiki/pages/viewpage.action?pageId=13893732
"""

from flask import request, current_app, g
from datetime import datetime
import re
from bson import ObjectId

from ..xin import Resource
from ..xin.tools import jsonify, abort
from ..xin.auth import requires_auth
from ..xin.snippets import Paginator, get_payload, get_resource, get_url_params
from ..xin.schema import relation, choice

from .utilisateurs import utilisateurs as utilisateurs_resource
from ..scripts import participation_generate_bilan

def validate_donnee_name(name):
    allow_extensions = ['wav', 'ta', 'tc', 'tac', 'tcc']
    try:
        basename, ext = name.rsplit('.', 1)
    except ValueError:
        return None
    if ext not in allow_extensions:
        return None
    # See rules: https://scille.atlassian.net/wiki/pages/viewpage.action?pageId=13893805
    if re.match(r'^Cir.+-[0-9]{4}-Pass[0-9]{1,2}-Tron[0-9]{1,2}-Chiro_([01]_)?[0-9]+_[0-9]{3}$', basename):
        # Protocole "routier" or "pedestre"
        pass_ = int(re.search(r'-Pass([0-9]{1,2})-', basename).group(1))
        # if pass_ > 10 or pass_ == 0:
        if pass_ == 0:
            return None
        tron = int(re.search(r'-Tron([0-9]{1,2})-', basename).group(1))
        # if tron > 15 or tron == 0:
        if tron == 0:
            return None
    elif re.match(r'^Car.+-[0-9]{4}-Pass[0-9]{1,2}-(([A-H][12])|(Z[1-9][0-9]*))-.*[0-9]{8}_[0-9]{6}_[0-9]{3}$', basename):
        # Protocole "point fixe"
        pass_ = int(re.search(r'-Pass([0-9]{1,2})-', basename).group(1))
        # if pass_ > 10 or pass_ == 0:
        if pass_ == 0:
            return None
    else:
        # Bad name
        return None
    return basename


SCHEMA = {
    'titre': {'type': 'string'},
    'commentaire': {'type': 'string'},
    'probleme': {'type': 'string'},
    'participation': relation('participations', required=True),
    'proprietaire': relation('utilisateurs', required=True),
    'publique': {'type': 'boolean'},
    'observations': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'temps_debut': {'type': 'float', 'required': True},
                'temps_fin': {'type': 'float', 'required': True},
                'frequence_mediane': {'type': 'float', 'required': True},
                'tadarida_taxon': relation('taxons', required=True),
                'tadarida_probabilite': {'type': 'float', 'required': True},
                'tadarida_taxon_autre': {
                    'type': 'list',
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'taxon': relation('taxons', required=True),
                            'probabilite': {'type': 'float', 'required': True}
                        }
                    }
                },
                'observateur_taxon': relation('taxons'),
                'observateur_probabilite': choice(['SUR', 'PROBABLE', 'POSSIBLE']),
                'validateur_taxon': relation('taxons'),
                'validateur_probabilite': choice(['SUR', 'PROBABLE', 'POSSIBLE']),
                'messages': {
                    'type': 'list',
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'message': {'type': 'string', 'required': True},
                            'auteur': relation('utilisateurs', required=True),
                            'date': {'type': 'datetime', 'required': True}
                        }
                    }
                }
            }
        }
    }
}


donnees = Resource('donnees', __name__, schema=SCHEMA)


def update_donnees_publique(user_id, donnees_publiques):
    if not isinstance(donnees_publiques, bool):
        raise RuntimeError('donnees_publiques must be a boolean')
    db = current_app.data.db[donnees.name]
    db.update_one({'proprietaire': user_id}, {'$set': {'publique': donnees_publiques}})


def _check_access_rights(donnee_resource):
    # Check access rights : admin, validateur and owner can read,
    # other can read only if the data is public
    if g.request_user['role'] not in ['Administrateur', 'Validateur']:
        is_owner = donnee_resource['proprietaire'] == g.request_user['_id']
        if not is_owner:
            # Check if owner authorizes public access
            owner = utilisateurs_resource.get_resource(donnee_resource['proprietaire'])
            if not owner.get('donnees_publiques', True):
                abort(403)


@donnees.route('/donnees', methods=['GET'])
@requires_auth(roles='Observateur')
def list_donnees():
    pagination = Paginator()
    if g.request_user['role'] in ['Administrateur', 'Validateur']:
        # Show all donnees for admin and validateurs
        lookup = None
    else:
        # Only show public and owned donnees
        lookup = {'$or': [{'publique': True}, {'proprietaire': g.request_user['_id']}]}
    found = donnees.find(lookup, skip=pagination.skip, limit=pagination.max_results)
    return pagination.make_response(*found)


@donnees.route('/donnees/<objectid:donnee_id>', methods=['GET'])
@requires_auth(roles='Observateur')
def display_donnee(donnee_id):
    donnee_resource = donnees.get_resource(donnee_id)
    _check_access_rights(donnee_resource)
    return donnee_resource


@donnees.route('/donnees/<objectid:donnee_id>/fichiers', methods=['GET'])
@requires_auth(roles='Observateur')
def display_donnee_fichiers(donnee_id):
    from .fichiers import (fichiers as fichiers_resource, ALLOWED_MIMES_TA,
                           ALLOWED_MIMES_TC, ALLOWED_MIMES_WAV)
    donnee_resource = donnees.get_resource(donnee_id)
    _check_access_rights(donnee_resource)
    lookup = {'lien_donnee': donnee_id}
    payload = get_url_params({'ta': {'type': bool, 'required': False},
                              'tc': {'type': bool, 'required': False},
                              'wav': {'type': bool, 'required': False}})
    if payload:
        mime = []
        if payload.get('ta', False):
            mime += ALLOWED_MIMES_TA
        if payload.get('tc', False):
            mime += ALLOWED_MIMES_TC
        if payload.get('wav', False):
            mime += ALLOWED_MIMES_WAV
        lookup['mime'] = {'$in': mime}
    pagination = Paginator()
    found = fichiers_resource.find(lookup, skip=pagination.skip, limit=pagination.max_results)
    return pagination.make_response(*found)


@donnees.route('/participations/<objectid:participation_id>/donnees', methods=['GET'])
@requires_auth(roles='Observateur')
def list_participation_donnees(participation_id):
    pagination = Paginator()
    lookup = {'participation': participation_id}
    if g.request_user['role'] not in ['Administrateur', 'Validateur']:
        # Only show public and owned donnees
        lookup['$or'] = [{'publique': True}, {'proprietaire': g.request_user['_id']}]
    if 'titre' in request.args:
        lookup.update({'titre': request.args['titre']})
    observations = {'observations': {'$elemMatch': {}}}
    if 'tadarida_taxon' in request.args:
        observations['observations']['$elemMatch'].update({'tadarida_taxon': ObjectId(request.args['tadarida_taxon'])})
        lookup.update(observations)
    found = donnees.find(lookup, skip=pagination.skip, limit=pagination.max_results,
                         projection={'participation': False, 'proprietaire': False})
    return pagination.make_response(*found)


@donnees.route('/participations/<objectid:participation_id>/donnees', methods=['POST'])
@requires_auth(roles='Observateur')
def create_donnee(participation_id):
    participation = get_resource('participations', participation_id)
    payload = get_payload({'commentaire': False, 'observations': False})
    payload['participation'] = participation_id
    payload['proprietaire'] = participation['observateur']
    # Only owner and admin can edit
    if g.request_user['_id'] != participation['observateur']:
        if g.request_user['role'] != 'Administrateur':
            abort(403)
        payload['publique'] = utilisateurs_resource.get_resource(payload['proprietaire']
            ).get('donnees_publiques', False)
    else:
        payload['publique'] = g.request_user.get('donnees_publiques', False)
    result = donnees.insert(payload)
    if 'observations' in payload and not request.args.get('no_bilan', False):
        participation_generate_bilan.delay_singleton(participation_id)
    return result, 201


@donnees.route('/donnees/<objectid:donnee_id>', methods=['PATCH'])
@requires_auth(roles='Observateur')
def update_donnee(donnee_id):
    payload = get_payload({'commentaire': False, 'probleme': False, 'observations': False})
    donnee_resource = donnees.get_resource(donnee_id)
    # Only admin (in fact script) can change that
    is_admin = g.request_user['role'] == 'Administrateur'
    if 'observations' in payload and not is_admin:
        abort(403)
    # Only owner and admin can edit
    if not is_admin and g.request_user['_id'] != donnee_resource['proprietaire']:
        abort(403)
    result =  donnees.update(donnee_id, payload)
    if 'observations' in payload and not request.args.get('no_bilan', False):
        participation_generate_bilan.delay_singleton(donnee_resource['participation'])
    return result, 200


@donnees.route('/donnees/<objectid:donnee_id>/observations/<int:observation_id>', methods=['PATCH'])
@requires_auth(roles='Observateur')
def edit_observation(donnee_id, observation_id):
    donnee_resource = donnees.get_resource(donnee_id)
    # Retrieve observation
    observations = donnee_resource.get('observations', [])
    if len(observations) <= observation_id:
        abort(404, 'Cannot retrieve observation {} of donnee {}'.format(
            observation_id, donnee_id))
    observation = observations[observation_id]
    payload = get_payload(['observateur_taxon', 'observateur_probabilite',
                           'validateur_taxon', 'validateur_probabilite'])
    mongo_update_observation = {}
    if 'observateur_taxon' in payload:
        # Only owner can set observateur_taxon
        if not donnee_resource['proprietaire'] == g.request_user['_id']:
            abort(403)
        if 'observateur_probabilite' not in payload:
            abort(422, {'observateur_probabilite': 'missing field'})
        observation['observateur_probabilite'] = payload.pop('observateur_probabilite')
        mongo_update_observation.update({
            'observations.%s.observateur_probabilite' % observation_id:
                observation['observateur_probabilite'],
            'observations.%s.observateur_taxon' % observation_id:
                ObjectId(payload.pop('observateur_taxon'))
        })
    if 'validateur_taxon' in payload:
        if g.request_user['role'] not in ['Administrateur', 'Validateur']:
            abort(403)
        if 'validateur_probabilite' not in payload:
            abort(422, {'validateur_probabilite': 'missing field'})
        observation['validateur_probabilite'] = payload.pop('validateur_probabilite')
        mongo_update_observation.update({
            'observations.%s.validateur_probabilite' % observation_id:
                observation['validateur_probabilite'],
            'observations.%s.validateur_taxon' % observation_id:
                ObjectId(payload.pop('validateur_taxon'))
        })
    if payload:
        abort(422, {f: 'unknown field' for f in payload.keys()})
    result = donnees.update(donnee_id, payload={'observations': [observation]},
                            mongo_update={'$set': mongo_update_observation})
    if not request.args.get('no_bilan', False):
        participation_generate_bilan.delay_singleton(donnee_resource['participation'])
    return result


@donnees.route('/donnees/<objectid:donnee_id>/observations/<int:observation_id>/messages', methods=['PUT'])
@requires_auth(roles='Observateur')
def comment_observation(donnee_id, observation_id):
    donnee_resource = donnees.get_resource(donnee_id)
    _check_access_rights(donnee_resource)
    # Retrieve observation
    observations = donnee_resource.get('observations', [])
    if len(observations) <= observation_id:
        abort(404, 'Cannot retrieve observation {} of donnee {}'.format(
            observation_id, donnee_id))
    observation = observations[observation_id]
    if 'messages' not in observation:
        observation['messages'] = []
    payload = get_payload({'message': True})
    if type(payload['message']) != str:
        abort(422, 'message must be string')
    message = {
        'auteur': g.request_user['_id'],
        'date': datetime.utcnow(),
        'message': payload['message']
    }
    observation['messages'].append(message)
    result = donnees.update(donnee_id, payload={'observations': [observation]},
        mongo_update={'$push':
            {'observations.{}.messages'.format(observation_id): message}
        }
    )
    return result
