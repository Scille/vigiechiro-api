
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
        'professionnel': {'type': 'string'},
        'donnees_publiques': {'type': 'boolean'},
        # Private data : tokens list
    }
}

# def check_auth(user, method):
#     if resource == 'utilisateurs':
#         if method == 'PUT':
#     print(token, allowed_roles, resource, method)
#     lookup = {'tokens': token}
#     if allowed_roles:
#         lookup['role'] = {'$in': allowed_roles}
#     accounts = app.data.driver.db['utilisateurs']
#     return accounts.find_one(lookup)
