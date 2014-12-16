SCHEMA = {
    'commentaire': {'type': 'string'},
    'localite': {'type': 'string', 'required': True},
    'participation': {'type': 'objectid', 'required': True},
    # TODO : create file type
    # 'fichier': {'type': 'File'},
    'date_fichier': {'type': 'date', 'required': True},
    'probleme': {'type': 'string'},
    'sous_probleme': {'type': 'string'},
    'taux_echantillonnage': {'type': 'integer'},
    'duree': {'type': 'integer'},
    'detection': {
        'type': 'dict',
        'schema': {
            # 'fichier': {'type': 'File', 'required': True},
            'version': {'type': 'string', 'required': True},
            # TODO : use regex OBSERVATEUR / SERVEUR
            'origine': {'type': 'string', 'required': True},
        },
        'observations': {
            'type': 'list',
            'schema': {
                'classification': {
                    'type': 'list',
                    'schema': {
                        'temps_debut': {'type': 'integer', 'required': True},
                        'temps_fin': {'type': 'integer', 'required': True},
                        'frequence_mediane': {'type': 'integer', 'required': True},
                        'tadarida_taxon': {'type': 'objectid', 'required': True},
                        'tadarida_probabilite': {'type': 'integer', 'required': True},
                        'tadarida_taxon_autre': {
                            'type': 'list',
                            'schema': {
                                'taxon': {'type': 'objectid', 'required': True},
                                'probabilite': {'type': 'integer', 'required': True}
                            }
                        },
                        'observateur_taxon': {'type': 'objectid'},
                        # SUR / PROBABLE / POSSIBLE
                        'observateur_probabilite': {'type': 'string'},
                        'validateur_taxon': {'type': 'objectid'},
                        # SUR / PROBABLE / POSSIBLE
                        'validateur_probabilite': {'type': 'string'},
                        'commentaire': {
                            'type': 'list',
                            'schema': {
                                'texte': {'type': 'string', 'required': True},
                                'auteur': {'type': 'objectid', 'required': True},
                                'date': {'type': 'date', 'required': True}
                            }
                        }
                    }
                }
            }
        }
    }
}

DOMAIN = {
    'item_title': 'site',
    'resource_methods': ['GET', 'POST'],
    'item_methods': ['GET', 'PUT'],
    'allowed_read_roles': ['Observateur'],
    'allowed_write_roles': ['Administrateur'],
    'schema': SCHEMA
}

__all__ = ['DOMAIN']
