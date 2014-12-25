from vigiechiro.xin import EveBlueprint
from .resource import relation, choice


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
                          url_prefix='/protocoles')
