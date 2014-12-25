from flask import app, current_app
from flask import abort, url_for, Blueprint, redirect
from functools import wraps
from flask import request, Response, g, abort
from cerberus.errors import ERROR_BAD_TYPE


def relation(resource, embeddable=True, field='_id', required=False):
    """Data model template for a resource relation"""
    return {'type': 'objectid',
            'data_relation': {
                'resource': resource,
                'field': field,
                'embeddable': embeddable
            }, 'required': required}


def choice(choices, required=False):
    """Data model template for a regex choice"""
    return {'type': 'string',
            'regex': r'^({})$'.format('|'.join(choices)),
            'required': required}
