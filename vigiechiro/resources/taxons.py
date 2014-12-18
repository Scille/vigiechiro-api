from flask import current_app as app
from flask import abort
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


TYPES = {}


def check_taxons_post(resources, items):
    for item in items:
        check_taxons(resources, item, None)


def check_taxons(resources, updates, original=None):
    # import pdb; pdb.set_trace()
    if 'parents' in updates:
        children = [original['_id']] if original else []
        def check_recur(children, curr_id):
            if curr_id in children:
                abort(422, "circular dependancy of parents"
                           " detected : {}".format(children))
            curr_doc = app.data.find_one('taxons', None, _id=curr_id)
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
