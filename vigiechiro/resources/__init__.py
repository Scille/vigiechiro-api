from .resource import Resource
from .fichier import Fichier
# from .donnee import Donnee
from .taxon import Taxon
from .utilisateur import Utilisateur
from .protocole import Protocole
from .site import Site
# from .participation import Participation


RESOURCES = [Utilisateur, Fichier, Taxon, Protocole, Site]


def generate_domain():
    return {ResourceCls.RESOURCE_NAME: ResourceCls.DOMAIN
            for ResourceCls in RESOURCES}


def register_app(app):
    for ResourceCls in RESOURCES:
        ResourceCls().register(app)
