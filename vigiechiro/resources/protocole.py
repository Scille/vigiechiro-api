"""
    Donnee protocole
    ~~~~~~~~~~~~~~~~

    see: https://scille.atlassian.net/wiki/pages/viewpage.action?pageId=13893673
"""

from flask import current_app, abort, jsonify
from bson import ObjectId
from datetime import datetime

from . import participation, actualite
from ..xin import EveBlueprint
from ..xin.auth import requires_auth
from ..xin.domain import relation, choice, get_resource


DOMAIN = {
    'item_title': 'protocole',
    'resource_methods': ['GET', 'POST'],
    'item_methods': ['GET', 'PATCH', 'PUT', 'DELETE'],
    'schema': {
        'titre': {'type': 'string', 'required': True},
        'description': {'type': 'string'},
        'parent': relation('protocoles', embeddable=False),
        'macro_protocole': {'type': 'boolean'},
        'tags': {
            'type': 'list',
            'schema': {'type': 'string'}
        },
        'fichiers': {
            'type': 'list',
            'schema': relation('fichiers', required=True),
        },
        'type_site': choice(['LINEAIRE', 'POLYGONE'], required=True),
        'taxon': relation('taxons', required=True),
        'configuration_participation': {
            'type': 'list',
            'schema': {'type': 'string'}
        },
        'algo_tirage_site': choice(['CARRE', 'ROUTIER', 'POINT_FIXE'], required=True)
    }
}


protocoles = EveBlueprint('protocoles', __name__, domain=DOMAIN,
                          auto_prefix=True)


def check_configuration_participation(payload):
    """
        Make sure the configuration provided is compatible with the data model
        of the participation
    """
    if 'configuration_participation' not in payload:
        return
    participation_configuration_fields = participation.get_configuration_fields()
    bad_keys = [key for key in payload['configuration_participation']
                if key not in participation_configuration_fields]
    if bad_keys:
        abort(422, "configuration_participation fields {}"
                   " are not valid".format(bad_keys))


@protocoles.event
def on_insert(items):
    for item in items:
        check_configuration_participation(item)


@protocoles.event
def on_replace(item, original):
    check_configuration_participation(item)


@protocoles.event
def on_update(updates, original):
    check_configuration_participation(updates)


@protocoles.route('/<protocole_id>/action/join', methods=['POST'])
@requires_auth(roles='Observateur')
def join_protocole(protocole_id):
    """Register the request user to the given protocole"""
    # Check if the user already joined the protocole
    protocoles = current_app.g.request_user.get('protocole', [])
    if next((p for p in protocoles if p['protocole'] == protocole_id), None):
        abort(422, "User already registered in protocole {}".format(protocole_id))
    protocole = get_resource('protocoles', protocole_id)
    # Cannot join a macro protocole
    if protocole.get('macro_protocole', False):
        abort(422, "Cannot join a macro protocole")
    # Finally update user's protocole list
    utilisateurs_db = current_app.data.driver.db['utilisateurs']
    utilisateurs_db.update({'_id': current_app.g.request_user['_id']},
                           {'$push': {'protocoles': {'protocole': ObjectId(protocole_id),
                                                     'date_inscription': datetime.utcnow()}}})
    actualite.create_actuality('INSCRIPTION_PROTOCOLE',
        sujet=current_app.g.request_user['_id'], objet=protocole_id)
    return jsonify({'_status': 'OK'})
