"""
    This module contains the definitions of the functional resources
"""

from importlib import import_module

from .utilisateurs import utilisateurs
from .taxons import taxons
from .protocoles import protocoles
from .fichiers import fichiers
from .grille_stoc import grille_stoc
from .actualites import actualites
from .sites import sites
from .participations import participations
from .donnees import donnees


def strip_resource_fields(doc_type, data):
    # I'm not proud of this...
    mapper = ('utilisateurs', 'taxons', 'protocoles', 'fichiers',
              'grille_stoc', 'actualites', 'sites', 'participations', 'donnees')
    if doc_type in mapper:
        module = import_module('vigiechiro.resources.%s' % doc_type)
        for field, info in module.SCHEMA.items():
            if info.get('hidden', False) and field in data:
                del data[field]
    return data
