"""
    Donnee grille_stoc
    ~~~~~~~~~~~~~~~~~~~~~

    wsg84 centroide data of France & DOM/TOM
"""

from ..xin import EveBlueprint


DOMAIN = {
    'item_title': 'site',
    'resource_methods': ['GET'],
    'item_methods': ['GET'],
    'allowed_read_roles': ['Observateur'],
    'allowed_item_read_roles': ['Observateur'],
    'schema': {
        'centre': {'type': 'point'},
        'numero': {'type': 'string'}
    }
}

grille_stoc = EveBlueprint('grille_stoc', __name__, domain=DOMAIN,
                           auto_prefix=True)
