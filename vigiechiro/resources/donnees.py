"""
    Donnee resource
    ~~~~~~~~~~~~~~~

    see: https://scille.atlassian.net/wiki/pages/viewpage.action?pageId=13893732
"""

from flask import request, current_app

from ..xin import Resource
from ..xin.tools import jsonify, abort
from ..xin.auth import requires_auth
from ..xin.snippets import Paginator, get_url_params
from ..xin.schema import relation, choice

SCHEMA = {
    'commentaire': {'type': 'string'},
    'localite': {'type': 'string', 'required': True},
    'participation': relation('utilisateurs', required=True),
    'fichier': relation('fichiers'),
    'date_fichier': {'type': 'date', 'required': True},
    'probleme': {'type': 'string'},
    'sous_probleme': {'type': 'string'},
    'taux_echantillonnage': {'type': 'integer'},
    'duree': {'type': 'integer'},
    'detection': {
        'type': 'dict',
        'schema': {
            'fichier': relation('fichiers', required=True),
            'version': {'type': 'string', 'required': True},
            'origine': choice(['OBSERVATEUR', 'SERVEUR'], required=True),
        },
    },
    'observations': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'classification': {
                    'type': 'list',
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'temps_debut': {'type': 'integer', 'required': True},
                            'temps_fin': {'type': 'integer', 'required': True},
                            'frequence_mediane': {'type': 'integer', 'required': True},
                            'tadarida_taxon': relation('taxons', required=True),
                            'tadarida_probabilite': {'type': 'integer', 'required': True},
                            'tadarida_taxon_autre': {
                                'type': 'list',
                                'schema': {
                                    'taxon': relation('taxons', required=True),
                                    'probabilite': {'type': 'integer', 'required': True}
                                }
                            },
                            'observateur_taxon': relation('taxons'),
                            'observateur_probabilite': choice(['SUR', 'PROBABLE', 'POSSIBLE']),
                            'validateur_taxon': relation('utilisateurs'),
                            'validateur_probabilite': choice(['SUR', 'PROBABLE', 'POSSIBLE']),
                            'commentaire': {
                                'type': 'list',
                                'schema': {
                                    'texte': {'type': 'string', 'required': True},
                                    'auteur': relation('utilisateurs', required=True),
                                    'date': {'type': 'date', 'required': True}
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

donnees = Resource('donnees', __name__, schema=SCHEMA)
