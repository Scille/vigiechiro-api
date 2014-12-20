from .resource import Resource
# from .donnee import Donnee
from .taxon import Taxon
from .utilisateur import Utilisateur
from .protocole import Protocole
from .site import Site
# from .participation import Participation

from eve.io.mongo.validation import Validator as EveValidator
from flask import current_app as app


def generate_domain(resources):
    return {resource.RESOURCE_NAME: resource.DOMAIN for resource in resources}
