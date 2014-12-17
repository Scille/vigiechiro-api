from flask import current_app as app
from eve.io.mongo.validation import Validator as EveValidator

DOMAIN = {
    'item_title': 'taxon',
    'resource_methods': ['GET', 'POST'],
    'item_methods': ['GET', 'PATCH', 'PUT'],
    'allowed_read_roles': ['Observateur'],
    'allowed_write_roles': ['Administrateur'],
    'allowed_item_read_roles': ['Observateur'],
    'allowed_item_write_roles': ['Administrateur'],
    'schema': {
        'libelle_long': {'type': 'string', 'required': True, 'unique': True},
        'libelle_court': {'type': 'string'},
        'description': {'type': 'string'},
        'parents': {
            'type': 'list',
            'schema': {
                'type': 'taxonsparentid',
                'data_relation': {
                    'resource': 'taxons',
                    'field': '_id',
                    'embeddable': False
                }
            }
        },
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


TYPES = {}

# def _validate_data_relation(self, data_relation, field, value):
#     EveValidator._validate_data_relation(self, data_relation, field, value)
#     data_resource = data_relation['resource']
#     for item in value:
#             query = {data_relation['field']: item}
#             if not app.data.find_one(data_resource, None, **query):
#                 self._error(
#                     field,
#                     "value '%s' must exist in resource"
#                     " '%s', field '%s'." %
#                     (item, data_resource, data_relation['field']))
