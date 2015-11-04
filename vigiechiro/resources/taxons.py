"""
    Donnee site
    ~~~~~~~~~~~

    see: https://scille.atlassian.net/wiki/pages/viewpage.action?pageId=13893670
"""

from ..xin import Resource
from ..xin.tools import jsonify, abort, dict_projection
from ..xin.auth import requires_auth
from ..xin.schema import relation
from ..xin.snippets import Paginator, get_payload, get_if_match, get_lookup_from_q


SCHEMA = {
    'libelle_long': {'type': 'string', 'required': True, 'unique': True},
    'libelle_court': {'type': 'string', 'required': True, 'unique': True},
    'description': {'type': 'string'},
    'parents': {
        'type': 'list',
        'schema': relation('taxons'),
        'non_recursive_dependancy': True
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


taxons = Resource('taxons', __name__, schema=SCHEMA)


@taxons.validator.attribute
def non_recursive_dependancy(context):
    if not context.schema['non_recursive_dependancy']:
        return
    own_id = context.additional_context.get('old_document', {}).get('_id', None)
    children = [own_id] if own_id else []
    def check_recur(children, curr_id):
        if curr_id in children:
            abort(422, "circular dependency of parents"
                       " detected : {}".format(children))
        curr_doc = taxons.get_resource(curr_id)
        if not curr_doc:
            abort(422, "parents ids leads to a broken parent"
                       " link '{}'".format(value, curr_parent))
        children.append(curr_id)
        for parent in curr_doc.get('parents', []):
            check_recur(children.copy(), parent)
    parents = context.value
    if len(set(parents)) != len(parents):
        abort(422, "Duplication in parents : {}".format(parents))
    for curr_id in parents:
        check_recur(children.copy(), curr_id)


def expend_parents_libelles(document):
    # TODO: this can be optimized by caching taxons' libelles
    if 'parents' not in document:
        return document
    parents = []
    for parent_id in document['parents']:
        parent = taxons.find_one({'_id': parent_id},
                                 {'libelle_long': 1, 'libelle_court': 1})
        if parent:
            parents.append(parent)
    document['parents'] = parents
    return document


@taxons.route('/taxons', methods=['GET'])
@requires_auth(roles='Observateur')
def list_taxons():
    pagination = Paginator()
    found = taxons.find(get_lookup_from_q(), skip=pagination.skip,
                        limit=pagination.max_results, sort=[('libelle_long', 1)])
    return pagination.make_response(*found)


@taxons.route('/taxons', methods=['POST'])
@requires_auth(roles='Administrateur')
def create_taxon():
    payload = get_payload()
    inserted_payload = taxons.insert(payload)
    return jsonify(inserted_payload), 201


@taxons.route('/taxons/<objectid:taxon_id>', methods=['GET'])
@requires_auth(roles='Observateur')
def display_taxon(taxon_id):
    return taxons.find_one({'_id': taxon_id})


@taxons.route('/taxons/<objectid:taxon_id>', methods=['PATCH'])
@requires_auth(roles='Administrateur')
def edit_taxon(taxon_id):
    return taxons.update(taxon_id, get_payload(), if_match=get_if_match())


@taxons.route('/taxons/liste', methods=['GET'])
@requires_auth(roles='Observateur')
def get_resume_list():
    """Return a brief list of per taxon id and libelle"""
    items = taxons.find({}, {"libelle_long": 1, 'libelle_court': 1})
    return {'_items': [i for i in items[0]]}
