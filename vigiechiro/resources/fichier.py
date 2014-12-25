"""
File upload module

see: https://devcenter.heroku.com/articles/s3-upload-python

The database only store some metadata about the file, which is uploaded&stored
in S3.
To upload a file, the user must first POST not the file but a manifest
containing basic informations about the file in order to get a signed url
to be allowed to upload the file to S3. Once done, a PATCH is requested to
notify that the file is complete.
"""

import base64
import urllib
import json
import time
import hmac
from hashlib import sha1
import uuid
import bson
import eve.render
from flask import request, abort, redirect, current_app
from eve.methods.post import post_internal

from .resource import relation
from vigiechiro.xin import EveBlueprint
from vigiechiro.xin.auth import requires_auth


DOMAIN = {
    'item_title': 'fichier',
    'item_methods': ['GET', 'PATCH', 'PUT'],
    'allowed_item_read_roles': ['Observateur'],
    'allowed_item_write_roles': ['Observateur'],
    'schema': {
        'proprietaire': relation('utilisateurs', required=True),
        'nom': {'type': 'string', 'required': True},
        'mime': {'type': 'string', 'required': True},
        'lien': {'type': 'url', 'required': True},
        'upload_realise': {'type': 'boolean'},
        'prive': {'type': 'boolean'}
    }
}
CONST_FIELDS = {'proprietaire', 'nom', 'mime', 'lien'}
fichiers = EveBlueprint('fichiers', __name__, domain=DOMAIN,
                        url_prefix='/fichiers')


@fichiers.event
def on_replace_fichiers(item, original):
    check_rights(original, item)


@fichiers.event
def on_fetched_item_fichiers(response):
    check_rights(response)


@fichiers.event
def on_update_fichiers(updates, original):
    check_rights(original, updates)


def check_rights(file_, updates=None):
    """Admin can do everything, owner can read/write, other users
       can only read if the data is not private
    """
    if current_app.g.request_user['role'] == 'Administrateur':
        return
    is_owner = file_['proprietaire'] == current_app.g.request_user['_id']
    if updates:
        if not is_owner:
            abort(403)
        if set(updates.keys()) & CONST_FIELDS:
            abort(403, 'not allowed to alter field(s) {}'.format(const_fields))
    else:
        if file_.get('prive', False) and not is_owner:
            abort(403)


@fichiers.route('/<file_id>/action/acces', methods=['GET'])
@requires_auth(roles='Observateur')
def access_s3(file_id):
    """Redirect to a signed url to get the file back from S3"""
    files_db = current_app.data.driver.db[fichiers.name]
    try:
        file_id = bson.ObjectId(file_id)
    except bson.errors.InvalidId:
        abort('Invalid ObjectId {}'.format(file_id), code=400)
    file_ = files_db.find_one({'_id': file_id})
    if not file_:
        abort(404)
    check_rights(file_)
    object_name = file_['nom']
    expires = int(time.time() + 10)
    get_request = "GET\n\n\n{}\n/{}/{}".format(
        expires,
        current_app.config['S3_BUCKET'],
        object_name)
    signature = base64.encodestring(
        hmac.new(current_app.config['AWS_SECRET'].encode(),
                 get_request.encode(), sha1).digest())
    signature = urllib.parse.quote_plus(signature.strip())
    url = 'https://{}.s3.amazonaws.com/{}'.format(
        current_app.config['S3_BUCKET'], object_name)
    return redirect('{}?AWSAccessKeyId={}&Expires={}&Signature={}'.format(
        url, current_app.config['AWS_KEY'], expires, signature), code=302)


@fichiers.route('/s3', methods=['POST'])
@requires_auth(roles='Observateur')
def sign_s3():
    """Return a signed url to let the user upload a file to s3"""
    object_name = uuid.uuid4().hex
    payload = request.json
    mime_type = payload.get('mime', '')
    expires = int(time.time() + 10)
    # TODO : change public-read is case of non-public file
    amz_headers = "x-amz-acl:public-read"
    put_request = "PUT\n\n{}\n{}\n{}\n/{}/{}".format(
        mime_type,
        expires,
        amz_headers,
        current_app.config['S3_BUCKET'],
        object_name)
    signature = base64.encodestring(
        hmac.new(
            current_app.config['AWS_SECRET'].encode(),
            put_request.encode(),
            sha1).digest())
    signature = urllib.parse.quote_plus(signature.strip())
    url = 'https://{}.s3.amazonaws.com/{}'.format(
        current_app.config['S3_BUCKET'],
        object_name)
    # Insert the file representation in the files resource
    payload['nom'] = object_name
    payload['proprietaire'] = current_app.g.request_user['_id']
    payload['lien'] = url
    response = post_internal('fichiers', payload)
    if response[-1] == 201:
        # signed_request is not stored in the database but transfered once
        response[0]['signed_request'] = '{}?AWSAccessKeyId={}&Expires={}&Signature={}'.format(
            url,
            current_app.config['AWS_KEY'],
            expires,
            signature)
    return eve.render.send_response('fichiers', response)
