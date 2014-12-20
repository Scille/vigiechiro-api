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


class Validator(EveValidator):

    def _validate_type_base64image(self, field, value):
        """Naive Base64 encoded png image type"""
        # TODO : check image validy and size
        if not value.startswith('data:image/png;base64,'):
            self._error(field, ERROR_BAD_TYPE % 'data:image/png;base64')
