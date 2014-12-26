import re
from flask import request, current_app
from eve.io.mongo.validation import Validator as EveValidator
from cerberus.errors import ERROR_BAD_TYPE, ERROR_READONLY_FIELD


class Validator(EveValidator):

    def _validate_type_url(self, field, value):
        if not re.match(r"^https?://", value):
            self._error(field, ERROR_BAD_TYPE % 'url')

    def _validate_postonly(self, read_only, field, value):
        """Field can be altered during POST only"""
        if current_app.g.request_user['role'] == 'Administrateur':
            return
        if read_only and request.method != 'POST':
            self._error(field, ERROR_READONLY_FIELD)

    def _validate_writerights(self, write_roles, field, value):
        """Limit write rights to write_roles"""
        if isinstance(write_roles, str):
            write_roles = [write_roles]
        if current_app.g.request_user['role'] not in write_roles:
            self._error(field, ERROR_READONLY_FIELD)
