"""
    Donnee participation
    ~~~~~~~~~~~~~~~~~~~~

    see: https://scille.atlassian.net/wiki/pages/viewpage.action?pageId=13893657
"""

from flask import abort, current_app

from vigiechiro.xin import EveBlueprint
from vigiechiro.xin.auth import requires_auth
from vigiechiro.xin.domain import relation, choice, get_resource


DOMAIN = {
    'item_title': 'participation',
    'resource_methods': ['GET', 'POST'],
    'item_methods': ['GET', 'PATCH', 'PUT'],
    'allowed_read_roles': ['Observateur'],
    'allowed_write_roles': ['Observateur'],
    'allowed_item_read_roles': ['Observateur'],
    'allowed_item_write_roles': ['Observateur'],
    'schema': {
        'observateur': relation('utilisateurs', required=True),
        'protocole': relation('protocoles', required=True),
        'site': relation('sites', required=True),
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
        'pieces_jointes': {
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
                # 'detecteur_enregistreur_type': {'type': 'custom_code'},
                'micro0_position': choice(['SOL', 'CANOPEE']),
                'micro0_numero_serie': {'type': 'string'},
                # 'micro0_type': {'type': 'custom_code'},
                'micro0_hauteur': {'type': 'integer'},
                'micro1_position': choice(['SOL', 'CANOPEE']),
                'micro1_numero_serie': {'type': 'string'},
                # 'micro1_type': {'type': 'custom_code'},
                'micro1_hauteur': {'type': 'integer'},
                # 'piste0_expansion': {'type': 'custom_code'},
                # 'piste1_expansion': {'type': 'custom_code'}
            }
        }
    }
}


participations = EveBlueprint('participations', __name__, domain=DOMAIN,
                              auto_prefix=True)


def _verify_participation_relations(payload):
    if (current_app.g.request_user['role'] != 'Administrateur' and
            current_app.g.request_user['_id'] != payload['observateur']):
        abort(422, 'only Administrateur can post for someone else')
    observateur = get_resource('utilisateurs', payload['observateur'])
    protocole = get_resource('protocoles', payload['protocole'])
    protocole_id = str(payload['protocole'])
    # Make sure the user has subscribed the protocole and is validated
    protocole_subscribe = next(
        (value for key,
         value in observateur.get(
             'protocoles',
             {}).items() if str(key) == protocole_id),
        None)
    if not protocole_subscribe:
        abort(422, "user hasn't subscribed to protocole {}".format(
            protocole['titre']))
    if not protocole_subscribe.get('valide', False):
        abort(
            422,
            "user cannot post to protocole {} until beeing validated".format(
                protocole['titre']))
    # Now check site is linked to the requested protocole
    site = get_resource('sites', payload['site'])
    if str(site['protocole']) != protocole_id:
        abort(422, "the site is not linked to protocole {}".format(
            protocole['titre']))


@participations.event
def on_insert(items):
    """
        New participation should only be issued by observateur registered
        and accepted for the given protocole.
    """
    for item in items:
        _verify_participation_relations(item)


@participations.event
def on_replace(item, original):
    """
        Check authorisations before replace:
         - Administrateur can modify all participations
         - Observateur can only modify it own participations
    """
    _verify_participation_relations(item)


@participations.event
def on_update(updates, original):
    """
        Check authorisations before update:
         - Administrateur can modify all participations
         - Observateur can only modify it own participations
    """
    # Only run the verification if update involves observateur/protocole/site
    verify_needed = False
    updates = updates.copy()
    for field in ('observateur', 'protocole', 'site'):
        if field in updates:
            verify_needed = True
        else:
            updates[field] = original[field]
    if verify_needed:
        _verify_participation_relations(updates)


def get_configuration_fields():
    return DOMAIN['schema']['configuration']['schema'].keys()


# @participations.route('/<participation_id>/action/commenter', methods=['GET'])
# @requires_auth(roles='Observateur')
# def comment(participation_id):
#     """Add a new comment to the given participation"""
#     participation_db = current_app.data.driver.db[participations.name]
#     try:
#         participation_id = bson.ObjectId(participation_id)
#     except bson.errors.InvalidId:
#         abort('Invalid ObjectId {}'.format(participation_id), code=400)
#     participation = participation_db.find_one({'_id': participation_id})
#     if not participation:
#         abort(404)
#     if 'posts' not in participation:
#         participation['posts'] = []
#     # participation['posts'].append(request.json)
#     check_rights(participation)
#     object_name = file_['nom']
#     expires = int(time.time() + 10)
#     get_request = "GET\n\n\n{}\n/{}/{}".format(
#         expires,
#         current_app.config['S3_BUCKET'],
#         object_name)
#     signature = base64.encodestring(
#         hmac.new(current_app.config['AWS_SECRET'].encode(),
#                  get_request.encode(), sha1).digest())
#     signature = urllib.parse.quote_plus(signature.strip())
#     url = 'https://{}.s3.amazonaws.com/{}'.format(
#         current_app.config['S3_BUCKET'], object_name)
#     return redirect('{}?AWSAccessKeyId={}&Expires={}&Signature={}'.format(
#         url, current_app.config['AWS_KEY'], expires, signature), code=302)
