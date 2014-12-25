from flask import abort
from vigiechiro.xin import EveBlueprint
from .resource import relation, choice
from . import participation


DOMAIN = {
    'item_title': 'protocole',
    'resource_methods': ['GET', 'POST'],
    'item_methods': ['GET', 'PATCH', 'PUT', 'DELETE'],
    'schema': {
        'titre': {'type': 'string', 'required': True},
        'description': {'type': 'string'},
        'parent': relation('protocoles', embeddable=False),
        'macro_protocole': {'type': 'boolean'},
        'tag': {
            'type': 'list',
            'schema': {'type': 'string'}
        },
        'fichiers': {
            'type': 'list',
            'schema': relation('fichiers', required=True),
        },
        'type_site': choice(['LINEAIRE', 'POLYGONE'], required=True),
        'taxon': relation('taxons'),
        'configuration_participation': {
            'type': 'list',
            'schema': {'type': 'string'}
        },
        'algo_tirage_site': choice(['CARRE', 'ROUTIER', 'POINT_FIXE'], required=True)
    }
}
protocoles = EveBlueprint('protocoles', __name__, domain=DOMAIN,
                          auto_prefix=True)


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


def check_configuration_participation(payload):
    if 'configuration_participation' not in payload:
        return
    participation_configuration_fields = participation.get_configuration_fields()
    bad_keys = [key for key in payload['configuration_participation']
                if key not in participation_configuration_fields]
    if bad_keys:
        abort(
            422,
            "configuration_participation fields {} are not valid".format(bad_keys))
