from flask import Blueprint
import eve.auth

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
            'participation': {
                                'type': 'objectid',
                                'data_relation': {
                                    'resource': 'utilisateurs',
                                    'field': '_id',
                                    'embeddable': True
                                },
                                'required': True
                            },
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
                    'origine': {
                        'type': 'string',
                        'regex': r'^(OBSERVATEUR|SERVEUR)$',
                        'required': True
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
                                'tadarida_taxon': {
                                    'type': 'objectid', 
                                    'data_relation': {
                                        'resource': 'utilisateurs',
                                        'field': '_id',
                                        'embeddable': True
                                    },
                                    'required': True
                                },
                                'tadarida_probabilite': {'type': 'integer', 'required': True},
                                'tadarida_taxon_autre': {
                                    'type': 'list',
                                    'schema': {
                                        'taxon': {
                                            'type': 'objectid', 
                                            'data_relation': {
                                                'resource': 'utilisateurs',
                                                'field': '_id',
                                                'embeddable': True
                                            },
                                            'required': True
                                        },
                                        'probabilite': {'type': 'integer', 'required': True}
                                    }
                                },
                                'observateur_taxon': {
                                    'type': 'objectid',
                                    'data_relation': {
                                        'resource': 'utilisateurs',
                                        'field': '_id',
                                        'embeddable': True
                                    }
                                },
                                'observateur_probabilite': {
                                    'type': 'string',
                                    'regex': r'^(SUR|PROBABLE|POSSIBLE)$',
                                },
                                'validateur_taxon': {
                                    'type': 'objectid', 
                                        'data_relation': {
                                            'resource': 'utilisateurs',
                                            'field': '_id',
                                            'embeddable': True
                                        }
                                    },
                                'validateur_probabilite': {
                                    'type': 'string',
                                    'regex': r'^(SUR|PROBABLE|POSSIBLE)$',
                                },
                                'commentaire': {
                                    'type': 'list',
                                    'schema': {
                                        'texte': {'type': 'string', 'required': True},
                                        'auteur': {
                                            'type': 'objectid',
                                            'data_relation': {
                                                'resource': 'utilisateurs',
                                                'field': '_id',
                                                'embeddable': True
                                            }
                                            'required': True
                                        },
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

    def __init__(self):
        super().__init__()
        @self.route('/donnees/<id>/action/archiver', methods=['POST'], allowed_roles=['Administrateur'])
        def donnees_archiver(id):
            # TODO : actualy do the archiving
            pass
