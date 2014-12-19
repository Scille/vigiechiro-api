from flask import current_app, abort

from .resource import Resource


class Taxon(Resource):
    RESOURCE_NAME = 'taxons'
    DOMAIN = {
        'item_title': 'taxon',
        'resource_methods': ['GET', 'POST'],
        'item_methods': ['GET', 'PATCH', 'PUT'],
        'schema': {
            'libelle_long': {'type': 'string', 'required': True, 'unique': True},
            'libelle_court': {'type': 'string', 'unique': True},
            'description': {'type': 'string'},
            'parents': {
                'type': 'list',
                'schema': {
                    'type': 'objectid',
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

    def _check_parents(self, updates, original=None):
        children = [original['_id']] if original else []
        def check_recur(children, curr_id):
            if curr_id in children:
                abort(422, "circular dependancy of parents"
                           " detected : {}".format(children))
            curr_doc = current_app.data.find_one('taxons', None, _id=curr_id)
            if not curr_doc:
                abort(422, "parents ids leads to a broken parent"
                           " link '{}'".format(value, curr_parent))
            children.append(curr_id)
            for parent in curr_doc.get('parents', []):
                check_recur(children.copy(), parent)
        parents = updates.get('parents', [])
        if len(set(parents)) != len(parents):
            abort(422, "Duplication in parents : {}".format(parents))
        for curr_id in parents:
            check_recur(children.copy(), curr_id)

    def __init__(self):
        super().__init__()
        @self.callback
        def on_insert(items):
            for item in items:
                self._check_parents(item)
        @self.callback
        def on_update(updates, original):
            self._check_parents(updates, original)
        @self.callback
        def on_replace(updates, original):
            self._check_parents(updates, original)
