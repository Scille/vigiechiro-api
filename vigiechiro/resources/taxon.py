from flask import current_app, abort

from vigiechiro.xin import EveBlueprint
from .resource import relation


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
            'schema': relation('taxons', embeddable=False),
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
        'photos': {
            'type': 'list',
            'schema': relation('fichiers', required=True)
        },
        'date_valide': {'type': 'datetime'},
    }
}
CONST_FIELDS = {'proprietaire', 'nom', 'mime', 'lien'}
taxons = EveBlueprint('taxons', __name__, domain=DOMAIN,
                      url_prefix='/taxons')


def check_parents(updates, original=None):
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


@taxons.event
def on_insert_taxons(items):
    for item in items:
        check_parents(item)


@taxons.event
def on_update_taxons(updates, original):
    check_parents(updates, original)


@taxons.event
def on_replace_taxons(updates, original):
    check_parents(updates, original)
