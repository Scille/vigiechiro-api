from .resource import Resource


class Protocole(Resource):
    RESOURCE_NAME = 'protocoles'
    DOMAIN = {
        'item_title': 'protocole',
        'resource_methods': ['GET', 'POST'],
        'item_methods': ['GET', 'PATCH', 'PUT', 'DELETE'],
        'schema': {
            'titre': {'type': 'string', 'required': True},
            'description': {'type': 'string'},
            'parent': {
                'type': 'objectid',
                'data_relation': {
                    'resource': 'protocoles',
                    'field': '_id',
                    'embeddable': False
                }
            },
            'macro_protocole': {'type': 'boolean'},
            'tag': {
                'type': 'list',
                'schema': {'type': 'string'}
            },
            # 'fichier': {'type': 'file'},
            'type_site': {'type': 'type_site_enum', 'required': True},
            'taxon': {
                'type': 'objectid',
                'data_relation': {
                    'resource': 'taxons',
                    'field': '_id',
                    'embeddable': True
                }
            },
            'configuration_participation': {
                'type': 'list',
                'schema': {'type': 'string'}
            },
            'algo_tirage_site': {'type': 'algo_tirage_site_enum'}
        }
    }

    def __init__(self):
        super().__init__()
        self.register_type_enum('type_site_enum', ('LINEAIRE', 'POLYGONE'))
        self.register_type_enum('algo_tirage_site_enum', ('CARRE', 'ROUTIER', 'POINT_FIXE'))
