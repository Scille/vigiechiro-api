"""
    Donnee resource
    ~~~~~~~~~~~~~~~

    see: https://scille.atlassian.net/wiki/pages/viewpage.action?pageId=13893732
"""

from flask import request, current_app, g
from datetime import datetime

from ..xin import Resource
from ..xin.tools import jsonify, abort
from ..xin.auth import requires_auth
from ..xin.snippets import Paginator, get_payload
from ..xin.schema import relation, choice

from .utilisateurs import utilisateurs as utilisateurs_resource


SCHEMA = {
    'commentaire': {'type': 'string'},
    # 'localite': {'type': 'string', 'required': True},
    'participation': relation('participations', required=True),
    'proprietaire': relation('utilisateurs', required=True),
    # 'fichier': relation('fichiers'),
    # 'date_fichier': {'type': 'date', 'required': True},
    # 'probleme': {'type': 'string'},
    # 'sous_probleme': {'type': 'string'},
    # 'taux_echantillonnage': {'type': 'integer'},
    # 'duree': {'type': 'integer'},
    # 'detection': {
    #     'type': 'dict',
    #     'schema': {
    #         'fichier': relation('fichiers', required=True),
    #         'version': {'type': 'string', 'required': True},
    #         'origine': choice(['OBSERVATEUR', 'SERVEUR'], required=True),
    #     },
    # },
    'observations': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'temps_debut': {'type': 'integer', 'required': True},
                'temps_fin': {'type': 'integer', 'required': True},
                'frequence_mediane': {'type': 'integer', 'required': True},
                'tadarida_taxon': relation('taxons', required=True),
                'tadarida_probabilite': {'type': 'integer', 'required': True},
                'tadarida_taxon_autre': {
                    'type': 'list',
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'taxon': relation('taxons', required=True),
                            'probabilite': {'type': 'integer', 'required': True}
                        }
                    }
                },
                'observateur_taxon': relation('taxons'),
                'observateur_probabilite': choice(['SUR', 'PROBABLE', 'POSSIBLE']),
                'validateur_taxon': relation('utilisateurs'),
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


@donnees.route('/donnees/<objectid:donnee_id>', methods=['GET'])
@requires_auth(roles='Observateur')
def display_donnee(donnee_id):
    donnee_resource = donnees.get_resource(donnee_id)
    _check_access_rights(donnee_resource)
    return donnee_resource


@donnees.route('/donnees', methods=['POST'])
@requires_auth(roles='Administrateur')
def create_donnee():
    payload = get_payload({'commentaire': False, 'participation': True,
                           'observations': False, 'proprietaire': False})
    if 'proprietaire' not in payload:
        payload['proprietaire'] = g.request_user['_id']
    return donnees.insert(payload), 201


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
        observation['observateur_taxon'] = payload.pop('observateur_taxon')
        mongo_update_observation.update({
            'observations.{}.observateur_probabilite': observation['observateur_probabilite'],
            'observations.{}.observateur_taxon': observation['observateur_taxon']
        })
    if 'validateur_taxon' in payload:
        if g.request_user['role'] not in ['Administrateur', 'Validateur']:
            abort(403)
        if 'validateur_probabilite' not in payload:
            abort(422, {'validateur_probabilite': 'missing field'})
        observation['validateur_probabilite'] = payload.pop('validateur_probabilite')
        observation['validateur_taxon'] = payload.pop('validateur_taxon')
        mongo_update_observation.update({
            'observations.{}.validateur_probabilite': observation['validateur_probabilite'],
            'observations.{}.validateur_taxon': observation['validateur_taxon']
        })
    if payload:
        abort(422, {f: 'unknown field' for f in payload.keys()})
    result = donnees.update(donnee_id, payload={'observations': [observation]},
                            mongo_update={'$set': mongo_update_observation})
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
