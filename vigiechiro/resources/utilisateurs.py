DOMAIN = {
    'item_title': 'utilisateur',
    'resource_methods': ['GET'],
    'item_methods': ['GET', 'PUT'],
    'allowed_read_roles': ['Observateur'],
    'allowed_write_roles': ['Administrateur'],
    'allowed_item_read_roles': ['Observateur'],
    'allowed_item_write_roles': ['Administrateur'],
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


def check_role(role, allowed_roles, rr):
    """
    Role are handled using least priviledge, thus a higher priviledged role
    also include it lower roles.
    """
    role_rules = {
        'Lecteur': ['Lecteur'],
        'Observateur': ['Lecteur', 'Observateur'],
        'Validateur': ['Lecteur', 'Observateur', 'Validateur'],
        'Administrateur': ['Lecteur', 'Observateur', 'Validateur', 'Administrateur']
    }
    print('in {} user : {} should be in {} ? {}'.format(rr, role, allowed_roles,
                                                        bool([r for r in role_rules[role] if r in allowed_roles])))
    return bool([r for r in role_rules[role] if r in allowed_roles])
