from .resource import Resource
from .fichier import fichiers
from .donnee import Donnee
from .taxon import taxons
from .utilisateur import utilisateurs
from .protocole import Protocole
from .site import sites
from .participation import Participation


RESOURCES = [Protocole]


def generate_domain():
    return {ResourceCls.RESOURCE_NAME: ResourceCls.DOMAIN
            for ResourceCls in RESOURCES}


def register_app(app):
    for ResourceCls in RESOURCES:
        ResourceCls().register(app)
