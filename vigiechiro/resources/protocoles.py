DOMAIN = {
    'item_title': 'protocole',
    'resource_methods': ['GET', 'POST'],
    'item_methods': ['GET', 'PATCH', 'PUT'],
    'allowed_read_roles': ['Observateur'],
    'allowed_write_roles': ['Administrateur'],
    'allowed_item_read_roles': ['Observateur'],
    'allowed_item_write_roles': ['Administrateur'],
    'schema': {
        'titre': {'type': 'string', 'required': True},
        'description': {'type': 'string'},
        'parent': {'type': 'objectid'},
        'macro_protocole': {'type': 'boolean'},
        'tag': {
            'type': 'list',
            'schema': {'type': 'string'}
        },
        # 'fichier': {'type': 'file'},
        # 'type_site': {'type': 'string', 'required': True},
        'taxon': {'type': 'objectid', 'required': True},
        'configuration_participation': {
            'type': 'list',
            'schema': {'type': 'string'}
        },
        'algo_tirage_site': {'type': 'string'} # CARRE | ROUTIER | POINT_FIXE
    }
}
