from .resource import relation, choice
from vigiechiro.xin import EveBlueprint


DOMAIN = {
    'item_title': 'participation',
    'resource_methods': ['GET', 'POST'],
    'item_methods': ['GET', 'PATCH', 'PUT'],
    'allowed_read_roles': ['Observateur'],
    'allowed_write_roles': ['Observateur'],
    'allowed_item_read_roles': ['Observateur'],
    'allowed_item_write_roles': ['Observateur'],
    'schema': {
        # 'numero': {'type': 'integer', 'required': True},
        'date_debut': {'type': 'datetime', 'required': True},
        'date_fin': {'type': 'datetime'},
        'meteo': {
            'type': 'dict',
            'schema': {
                'temperature_debut': {'type': 'integer'},
                'temperature_fin': {'type': 'integer'},
                'vent': choice(['NUL', 'FAIBLE', 'MOYEN', 'FORT']),
                'couverture': choice(['0-25', '25-50', '50-75', '75-100']),
            }
        },
        'commentaire': {'type': 'string'},
        'piece_jointe': {
            'type': 'list',
            'schema': relation('fichiers', required=True)
        },
        'posts': {
            'type': 'list',
            'schema': {
                'auteur': relation('utilisateurs', required=True),
                'message': {'type': 'string', 'required': True},
                'date': {'type': 'datetime', 'required': True},
            }
        },
        'configuration': {
            'type': 'dict',
            'schema': {
                'detecteur_enregistreur_numero_serie': {'type': 'string'},
                # TODO : create the custom_code type (dynamically
                # parametrized regex)
                'detecteur_enregistreur_type': {'type': 'custom_code'},
                'micro0_position': choice(['SOL', 'CANOPEE']),
                'micro0_numero_serie': {'type': 'string'},
                'micro0_type': {'type': 'custom_code'},
                'micro0_hauteur': {'type': 'integer'},
                'micro1_position': choice(['SOL', 'CANOPEE']),
                'micro1_numero_serie': {'type': 'string'},
                'micro1_type': {'type': 'custom_code'},
                'micro1_hauteur': {'type': 'integer'},
                'piste0_expansion': {'type': 'custom_code'},
                'piste1_expansion': {'type': 'custom_code'}
            }
        },
        'observateur': relation('utilisateurs', required=True),
        'site': relation('sites', required=True)
    }
}
participations = EveBlueprint('participations', __name__, domain=DOMAIN,
                              url_prefix='/participations')
