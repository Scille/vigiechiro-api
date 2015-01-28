"""
    Donnee site
    ~~~~~~~~~~~

    see: https://scille.atlassian.net/wiki/pages/viewpage.action?pageId=13893670
"""

from flask import current_app, abort

from ..xin import EveBlueprint, jsonify
from ..xin.auth import requires_auth
from ..xin.domain import relation


DOMAIN = {
    'item_title': 'taxon',
    'resource_methods': ['GET', 'POST'],
    'item_methods': ['GET', 'PATCH', 'PUT'],
    'schema': {
        'libelle_long': {'type': 'string', 'required': True, 'unique': True},
        'libelle_court': {'type': 'string', 'required': True, 'unique': True},
        'description': {'type': 'string'},
        'parents': {
            'type': 'list',
            'schema': relation('taxons', embeddable=True),
        },
        'liens': {
            'type': 'list',
            'schema': {'type': 'url'}
        },
        'tags': {
            'type': 'list',
            'schema': {'type': 'string'}
        },
        'photos': {
            'type': 'list',
            'schema': relation('fichiers', required=True)
        },
        'date_valide': {'type': 'datetime'},
    }
}
CONST_FIELDS = {'proprietaire', 'nom', 'mime', 'lien'}
taxons = EveBlueprint('taxons', __name__, domain=DOMAIN,
                      auto_prefix=True)


def _check_parents(updates, original=None):
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
def on_insert(items):
    for item in items:
        _check_parents(item)


@taxons.event
def on_update(updates, original):
    _check_parents(updates, original)


@taxons.event
def on_replace(updates, original):
    _check_parents(updates, original)


@taxons.route('/liste', methods=['GET'])
@requires_auth(roles='Observateur')
def get_resume_list():
    """Return a brief list of per taxon id and libelle"""
    items = current_app.data.driver.db['taxons'].find({}, {"libelle_long": 1})
    return jsonify(_items=[i for i in items])
