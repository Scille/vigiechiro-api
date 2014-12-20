import re
from eve.io.mongo.validation import Validator as EveValidator
from cerberus.errors import ERROR_BAD_TYPE


class Validator(EveValidator):

    def _validate_type_base64image(self, field, value):
        """Naive Base64 encoded png image type"""
        # TODO : check image validy and size
        if not value.startswith('data:image/png;base64,'):
            self._error(field, ERROR_BAD_TYPE % 'data:image/png;base64')

    def _validate_type_url(self, field, value):
        if not re.match(r"^https?://", value):
            self._error(field, ERROR_BAD_TYPE % 'url')
