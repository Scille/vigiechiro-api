"""
    File upload
    ~~~~~~~~~~~

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
import logging
import hmac
from hashlib import sha1
import uuid
import bson
import eve.render
from flask import request, abort, redirect, current_app
from eve.methods.post import post_internal
import requests
import boto
import re

from ..xin import EveBlueprint, jsonify
from ..xin.auth import requires_auth
from ..xin.domain import relation, get_resource


DOMAIN = {
    'item_title': 'fichier',
    'item_methods': ['GET', 'PATCH', 'PUT', 'DELETE'],
    'resource_methods': ['GET'],
    'allowed_item_read_roles': ['Observateur'],
    'allowed_item_write_roles': ['Observateur'],
    'allowed_write_roles': ['Observateur'],
    'schema': {
        'proprietaire': relation('utilisateurs', postonly=True, required=True),
        'titre': {'type': 'string', 'postonly': True, 'required': True},
        'S3_id': {'type': 'string', 'postonly': True},
        'S3_upload_id': {'type': 'string', 'postonly': True},
        'S3_upload_realise': {'type': 'boolean'},
        'mime': {'type': 'string', 'postonly': True, 'required': True},
        'prive': {'type': 'boolean'}
    }
    # TODO : add projection on S3...
}
CONST_FIELDS = {'proprietaire', 'titre', 'mime', 'lien'}
fichiers = EveBlueprint('fichiers', __name__, domain=DOMAIN,
                        auto_prefix=True)


def _check_rights(file_, updates=None):
    """Admin can do everything, owner can read/write, other users
       can only read if the data is not private
    """
    if current_app.g.request_user['role'] == 'Administrateur':
        return
    is_owner = file_['proprietaire'] == current_app.g.request_user['_id']
    if updates:
        if not is_owner:
            abort(403)
    else:
        if file_.get('prive', False) and not is_owner:
            abort(403)


def _sign_request(**kwargs):
    verb = kwargs.pop('verb', 'GET')
    content_md5 = kwargs.pop('content_md5', '')
    content_type = kwargs.pop('content_type', '')
    expires = kwargs.pop('expires', int(time.time() + 10))
    amz_headers = kwargs.pop('amz_headers', '')
    params = kwargs.pop('params', {})
    sign_head = kwargs.pop('sign_head', {})
    flat_params = ''
    if params:
        for key, value in params.items():
            if value:
                flat_params += '{}={}&'.format(key, value)
            else:
                flat_params += '{}&'.format(key)
    if isinstance(amz_headers, dict):
        amz_headers = '\n'.join(["{}:{}".format(key.lower(), amz_headers[key])
                                 for key in sorted(amz_headers.keys())])
    if amz_headers:
        amz_headers += '\n'
    bucket = kwargs.pop('bucket', current_app.config['AWS_S3_BUCKET'])
    object_name = kwargs.pop('object_name', '')
    s3_path = '/{}/{}'.format(bucket, object_name) if bucket else '/' + object_name
    if sign_head:
        s3_path += '?' + sign_head
    s3_request = "{}\n{}\n{}\n{}\n{}{}".format(
        verb, content_md5, content_type, expires, amz_headers, s3_path)
    signature = base64.encodestring(hmac.new(
            current_app.config['AWS_SECRET_ACCESS_KEY'].encode(),
            s3_request.encode(),
            sha1).digest())
    signature = urllib.parse.quote_plus(signature.strip())
    s3_url = 'https://{}.s3.amazonaws.com/{}'.format(
        current_app.config['AWS_S3_BUCKET'], object_name)
    if sign_head:
        cooked_sign_head = '?' + sign_head + '&'
    else:
        cooked_sign_head = '?'
    sign = {
        'url': s3_url,
        'params': params,
        'signed_url': (s3_url + cooked_sign_head + flat_params +
            'AWSAccessKeyId={}&Expires={}&Signature={}'.format(
                current_app.config['AWS_ACCESS_KEY_ID'], expires, signature))
    }
    return sign


@fichiers.event
def on_replace(item, original):
    _check_rights(original, item)


@fichiers.event
def on_fetched_item(response):
    _check_rights(response)


@fichiers.event
def on_update(updates, original):
    _check_rights(original, updates)


@fichiers.route('/<file_id>/multipart/annuler', methods=['DELETE'])
@requires_auth(roles='Observateur')
def s3_multipart_cancel(file_id):
    file_ = get_resource('fichiers', file_id)
    if 'S3_id' not in file_ or 'S3_upload_id' not in file_:
        abort(422, 'file is not a S3 multipart')
    if file_.get('S3_upload_realise', False):
        abort(422, 'Can only delete fichiers during S3 multipart upload')
    object_name = file_['S3_id']
    sign = _sign_request(verb='DELETE', object_name=object_name,
                         sign_head='uploadId={}'.format(file_['S3_upload_id']))
    r = requests.delete(sign['signed_url'])
    if r.status_code != 204:
        logging.error('S3 {} error {} : {}'.format(sign['signed_url'], r.status_code, r.text))
        abort(500, 'S3 has rejected file creation request')
    db = current_app.data.driver.db['fichiers']
    db.remove({'_id': file_['_id']})
    return jsonify({'_status': 'ok', 'signed_request': sign['signed_url']})


@fichiers.route('/s3/multipart', methods=['POST'])
@requires_auth(roles='Observateur')
def s3_multipart_create():
    """Return a signed url to let the user upload a file to s3"""
    object_name = uuid.uuid4().hex
    # Insert the file representation in the files resource
    payload = request.json
    payload['proprietaire'] = current_app.g.request_user['_id']
    payload['S3_id'] = object_name
    # TODO : add metadata
    amz_headers = {'x-amz-meta-title': payload.get('titre', '')}
    amz_headers['Content-Type'] = payload.get('mime', '')
    sign = _sign_request(verb='POST', object_name=object_name,
                         content_type=payload.get('mime', ''),
                         sign_head='uploads')
    r = requests.post(sign['signed_url'], headers={'Content-Type': payload.get('mime', '')})
    if r.status_code != 200:
        logging.error('S3 {} error {} : {}'.format(sign['signed_url'], r.status_code, r.text))
        abort(500, 'S3 has rejected file creation request')
    # Why AWS doesn't provide a JSON api ???
    payload['S3_upload_id'] = re.search('<UploadId>(.+)</UploadId>', r.text).group(1)
    response = post_internal('fichiers', payload)
    return eve.render.send_response('fichiers', response)


@fichiers.route('/<file_id>/multipart/continue', methods=['PUT'])
@requires_auth(roles='Observateur')
def s3_multipart_continue(file_id):
    file_ = get_resource('fichiers', file_id)
    payload = request.json
    if 'part_number' not in payload:
        abort(422, 'missing field part_number')
    if 'S3_id' not in file_ or 'S3_upload_id' not in file_:
        abort(422, 'file is not a S3 multipart')
    object_name = file_['S3_id']
    sign = _sign_request(verb='PUT', object_name=object_name,
                         sign_head='partNumber={}&uploadId={}'.format(
                            payload['part_number'], file_['S3_upload_id'])
                        )
    return jsonify({'_status': 'ok', 'signed_request': sign['signed_url']})


@fichiers.route('/<file_id>/multipart/terminer', methods=['PUT'])
@requires_auth(roles='Observateur')
def s3_multipart_end(file_id):
    payload = request.json
    if 'parts' not in payload:
        abort(422, 'missing field parts')
    file_ = get_resource('fichiers', file_id)
    if 'S3_id' not in file_ or 'S3_upload_id' not in file_:
        abort(422, 'file is not a S3 multipart')
    # Build xml payload
    xml_body = '<CompleteMultipartUpload>'
    content_type = 'application/xml; charset=UTF-8'
    for part in payload['parts']:
        if set(part.keys()) != set(['part_number', 'etag']):
            abort(422, 'invalid parts list')
        xml_body += ('<Part><PartNumber>' + str(part['part_number']) +
                     '</PartNumber><ETag>' + str(part['etag']) + '</ETag></Part>')
    xml_body += '</CompleteMultipartUpload>'
    sign = _sign_request(verb='POST', object_name=file_['S3_id'],
                         content_type=content_type,
                         sign_head='uploadId='+file_['S3_upload_id']
                        )
    r = requests.post(sign['signed_url'],
                     headers={'Content-Type': content_type},
                     data=xml_body)
    if r.status_code != 200:
        logging.error('Completing {} error {} : {}'.format(
            sign['signed_url'], r.status_code, r.text))
        abort(500, 'Error with S3')
    db = current_app.data.driver.db['fichiers']
    db.update({'_id': file_['_id']}, {'$set': {'S3_upload_realise': True}})
    return jsonify({'_status': 'ok'})


@fichiers.route('/<file_id>/action/acces', methods=['GET'])
@requires_auth(roles='Observateur')
def s3_access_file(file_id):
    """Redirect to a signed url to get the file back from S3"""
    file_ = get_resource('fichiers', file_id)
    _check_rights(file_)
    if 'S3_id' not in file_ or not file_.get('S3_upload_realise', False):
        abort(410, 'file is not available')
    object_name = file_['S3_id']
    sign = _sign_request(verb='GET', object_name=object_name)
    return redirect(sign['signed_url'], code=302)


@fichiers.route('/s3', methods=['POST'])
@requires_auth(roles='Observateur')
def s3_create():
    """Return a signed url to let the user upload a file to s3"""
    object_name = uuid.uuid4().hex
    payload = request.json
    mime_type = payload.get('mime', '')
    sign = _sign_request(verb='PUT', object_name=object_name,
                         content_type=mime_type)
    # Insert the file representation in the files resource
    payload['S3_id'] = object_name
    payload['proprietaire'] = current_app.g.request_user['_id']
    response = post_internal('fichiers', payload)
    if response[-1] == 201:
        # signed_request is not stored in the database but transfered once
        response[0]['signed_request'] = sign['signed_url']
    return eve.render.send_response('fichiers', response)
