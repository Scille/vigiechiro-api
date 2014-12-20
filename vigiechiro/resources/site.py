from flask import current_app, abort, jsonify

from .resource import Resource

STOC_SCHEMA = {
    'subdivision1': {'type': 'string', 'regex': r'^()$'},
    'subdivision2': {'type': 'string', 'regex': r'^()$'},
    'subdivision3': {'type': 'string', 'regex': r'^()$'},
    'subdivision4': {'type': 'string', 'regex': r'^()$'},
    'subdivision5': {'type': 'string', 'regex': r'^()$'},
    'subdivision6': {'type': 'string', 'regex': r'^()$'}
}


class Site(Resource):
    RESOURCE_NAME = 'sites'
    DOMAIN = {
        'item_title': 'site', 'resource_methods': [
            'GET', 'POST'], 'item_methods': [
            'GET', 'PATCH', 'PUT'], 'schema': {
                'numero': {
                    'type': 'integer', 'required': True}, 'protocole': {
                        'type': 'objectid', 'data_relation': {
                            'resource': 'protocoles', 'field': '_id', 'embeddable': False}, 'commentaire': {
                                'type': 'string'}, 'numero_grille_stoc': {
                                    'type': 'string'}, 'verrouiller': {
                                        'type': 'boolean'}, 'coordonnee': {
                                            'type': 'point'}, 'url_cartographie': {
                                                'type': 'url'}, 'largeur': {
                                                    'type': 'number'}, 'localite': {
                                                        'type': 'list', 'schema': {
                                                            'coordonnee': {
                                                                'type': 'point'}, 'representatif': {
                                                                    'type': 'boolean'}, 'habitat': {
                                                                        'type': 'dict', 'schema': {
                                                                            'date': {
                                                                                'type': 'datetime'}, 'stoc_principal': {
                                                                                    'type': 'dict', 'schema': STOC_SCHEMA}, 'stoc_secondaire': {
                                                                                        'type': 'dict', 'schema': STOC_SCHEMA}}}}}, 'type_site': {
                                                                                            'type': 'string', 'regex': r'^(LINEAIRE|POLYGONE)$'}, 'generee_aleatoirement': {
                                                                                                'type': 'boolean'}, 'justification_non_aleatoire': {
                                                                                                    'type': 'string'}}}}

    def __init__(self):
        super().__init__()

        @self.route('/stoc', methods=['GET'])
        def display_stock():
            return jsonify(STOC_SCHEMA)
