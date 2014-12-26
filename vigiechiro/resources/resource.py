from flask import abort, current_app
import bson


def relation(resource, embeddable=True, field='_id', **kwargs):
    """Data model template for a resource relation"""
    kwargs.update({'type': 'objectid',
                   'data_relation': {
                       'resource': resource,
                       'field': field,
                       'embeddable': embeddable
                   }
                   })
    return kwargs


def get_resource(resource, id):
    """Retrieve object from database with it ID and resource name"""
    try:
        id = bson.ObjectId(id)
    except bson.errors.InvalidId:
        abort(422, 'Invalid ObjectId {}'.format(id))
    db = current_app.data.driver.db[resource]
    obj = db.find_one({'_id': id})
    if not obj:
        abort(422, '{} is not a vaild {} resource'.format(id, resource))
    return obj


def choice(choices, **kwargs):
    """Data model template for a regex choice"""
    kwargs.update({'type': 'string',
                   'regex': r'^({})$'.format('|'.join(choices))})
    return kwargs
