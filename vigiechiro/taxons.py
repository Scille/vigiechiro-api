DOMAIN = {
    'item_title': 'taxon',
    'resource_methods': ['GET', 'POST'],
    'item_methods': ['GET', 'PATCH', 'PUT'],
    'allowed_read_roles': ['Observateur'],
    'allowed_write_roles': ['Administrateur'],
    'schema': {
        'libelle_long': {'type': 'string', 'required': True},
        'libelle_court': {'type': 'string'},
        'description': {'type': 'string'},
        'parent': {'type': 'objectid'},
        'liens': {
            'type': 'list',
            'schema': {'type': 'string'}
        },
        'tags': {
            'type': 'list',
            'schema': {'type': 'string'}
        },
        # TODO : use more robust file type
        'photos': {'type': 'list', 'schema': {'type': 'base64image'}},
        'date_valide': {'type': 'datetime'},
    }
}
