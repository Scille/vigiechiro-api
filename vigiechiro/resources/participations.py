DOMAIN = {
    'item_title': 'participation',
    'resource_methods': ['GET', 'POST'],
    'item_methods': ['GET', 'PATCH', 'PUT'],
    'allowed_read_roles': ['Observateur'],
    'allowed_write_roles': ['Administrateur'],
    'allowed_item_read_roles': ['Observateur'],
    'allowed_item_write_roles': ['Administrateur'],
    'schema': {
        'numero': {'type': 'objectid'}
    }
}
