from .resource import Resource, relation, choice


class Donnee(Resource):
    DOMAIN = {
        'item_title': 'site',
        'resource_methods': ['GET', 'POST'],
        'item_methods': ['GET', 'PUT'],
        'allowed_read_roles': ['Observateur'],
        'allowed_write_roles': ['Observateur'],
        'schema': {
            'commentaire': {'type': 'string'},
            'localite': {'type': 'string', 'required': True},
            'participation': relation('participations', required=True),
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
                    'classification': {
                        'type': 'list',
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

    def __init__(self):
        super().__init__()

        @self.route('/<id>/action/archiver', methods=['POST'],
                    allowed_roles=['Administrateur'])
        def donnees_archiver(id):
            # TODO : actualy do the archiving
            pass
