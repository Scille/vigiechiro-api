DOMAIN = {
    'item_title': 'utilisateur',
    'resource_methods': ['GET'],
    'item_methods': ['GET', 'PUT'],
    'allowed_roles': ['Observateur'],
    'schema': {
        'pseudo': {'type': 'string', 'required': True},
        'email': {'type': 'string', 'required': True},
        'nom': {'type': 'string'},
        'prenom': {'type': 'string'},
        'telephone': {'type': 'string'},
        'adresse': {'type': 'string'},
        'commentaire': {'type': 'string'},
        'organisation': {'type': 'string'},
        'tag': {
            'type': 'list',
            'schema': {'type': 'string'}
        },
        'professionnel': {'type': 'boolean'},
        'donnees_publiques': {'type': 'boolean'},
        # Private data : tokens list
    }
}

def check_role(role, allowed_roles):
    """
    Role are handled using least priviledge, thus a higher priviledged role
    also include it lower roles.
    """
    role_rules = {
        'Observateur': ['Observateur'],
        'Validateur': ['Observateur', 'Validateur'],
        'Administrateur': ['Observateur', 'Validateur', 'Administrateur']
    }
    return bool([r for r in role_rules[role] if r in allowed_roles])
