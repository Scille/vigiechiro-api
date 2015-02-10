"""
    Donnee actualité
    ~~~~~~~~~~~~~~~~

"""

from datetime import datetime
from flask import current_app

from ..xin import EveBlueprint
from ..xin.domain import relation, choice


DOMAIN = {
    'item_title': 'actualite',
    'resource_methods': ['GET'],
    'item_methods': ['GET'],
    'schema': {
        'resources': {
            'type': 'list',
            'schema': {'type': 'objectid'}
        },
        'action':  choice(['INSCRIPTION_PROTOCOLE',
                           'NOUVEAU_SITE',
                           'NOUVELLE_PARTICIPATION']),
        'sujet': relation('utilisateurs'),
        'objet': {'type': 'objectid'}
    }
}


actualites = EveBlueprint('actualites', __name__, domain=DOMAIN,
                          auto_prefix=True)


def create_actuality(action, sujet, objet, resources=None):
    """Create a new actuality"""
    if not resources:
        resources = [sujet, objet]
    document = {'resources': resources, 'action': action}
    # TODO : check validity of objecIds
    if sujet:
        document['sujet'] = sujet
    if objet:
        document['objet'] = objet
    document[current_app.config['LAST_UPDATED']] = \
        document[current_app.config['DATE_CREATED']] = datetime.utcnow().replace(microsecond=0)
    current_app.data.driver.db['actualites'].insert(document)
