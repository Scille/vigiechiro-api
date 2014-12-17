from . import donnees
from . import taxons
from . import utilisateurs
from . import protocoles
from . import participations
from eve.io.mongo.validation import Validator as EveValidator
from flask import current_app as app


DOMAIN = {
    'utilisateurs': utilisateurs.DOMAIN,
    'taxons': taxons.DOMAIN,
    'donnees': donnees.DOMAIN,
    'protocoles': protocoles.DOMAIN,
    'participations': participations.DOMAIN
}


BLUEPRINTS = [donnees.BLUEPRINT]


def meta_validator(name, bases, dct):
    # Dynamically add custom types
    for validator in [taxons.TYPES]:
        for key, func in validator.items():
            print('inserting validator {}'.format('_validate_type_' + key))
            dct['_validate_type_' + key] = func
    return type(name, bases, dct)


class Validator(EveValidator, metaclass=meta_validator):

    def _validate_type_taxonsparentid(self, field, value):
        self._validate_type_objectid(field, value)
        # if self._error:
        #     return
        print('===> taxon {}/{} (id : {})'.format(field, value, self._id))
        parents = [self._id] if self._id else []
        to_check_parents = [value]
        for curr_parent in to_check_parents:
            if curr_parent in parents:
                self._error(field, "id '{}' leads to a circular"
                                   " dependancy of parents.".format(value))
                break
            parents.append(curr_parent)
            # Get back the parent taxon and process it own parents
            parent_doc = app.data.find_one('taxons', None, _id=curr_parent)
            if not parent_doc:
                self._error(field, "id '{}' leads to a broken parent"
                                   " link '{}'".format(value, curr_parent))
                break
            to_check_parents += parent_doc.get('parents', [])

    def _validate_type_base64image(self, field, value):
        """Naive Base64 encoded png image type"""
        # TODO : check image validy and size
        if not value.startswith('data:image/png;base64,'):
            self._error(field, ERROR_BAD_TYPE % 'data:image/png;base64')
