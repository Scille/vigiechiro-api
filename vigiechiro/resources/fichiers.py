"""
    File upload
    ~~~~~~~~~~~

    see: https://devcenter.heroku.com/articles/s3-upload-python

    The database only store some metadata about the file, which is
    uploaded&stored in S3.
    To upload a file, the user must first POST not the file but a manifest
    containing basic informations about the file in order to get a signed url
    to be allowed to upload the file to S3. Once done, a PATCH is requested to
    notify that the file is complete.
"""

import base64
import urllib
import time
import logging
import hmac
from hashlib import sha1
import uuid
from flask import request, abort, current_app, g, redirect
import requests
import re

from ..xin import Resource
from ..xin.tools import jsonify, abort
from ..xin.auth import requires_auth
from ..xin.schema import relation, choice
from ..xin.snippets import get_payload
from .utilisateurs import utilisateurs as utilisateurs_resource


SCHEMA = {
    'titre': {'type': 'string', 'postonly': True, 'required': True},
    'mime': {'type': 'string', 'postonly': True, 'required': True},
    'proprietaire': relation('utilisateurs', postonly=True, required=True),
    'disponible': {'type': 'boolean'},
    's3_id': {'type': 'string', 'postonly': True},
    's3_upload_multipart_id': {'type': 'string', 'postonly': True},
    's3_upload_done': {'type': 'boolean'},
    'require_process': choice(['tadarida_d', 'tadarida_c']),
    'lien_participation': relation('participations'),
    'lien_protocole': relation('protocoles')
}


fichiers = Resource('fichiers', __name__, schema=SCHEMA)


def _check_access_rights(file_resource):
    # Check access rights : admin, validateur and owner can read,
    # other can read only if the data is public
    if g.request_user['role'] not in ['Administrateur', 'Validateur']:
        is_owner = file_resource['proprietaire'] == g.request_user['_id']
        if not is_owner:
            # Check if owner authorizes public access
            owner = utilisateurs_resource.get_resource(file_resource['proprietaire'])
            if not owner.get('donnees_publiques', True):
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


@fichiers.route('/fichiers/<objectid:fichier_id>', methods=['GET'])
@requires_auth(roles='Observateur')
def display_fichier(fichier_id):
    file_resource = fichiers.get_resource(fichier_id)
    _check_access_rights(file_resource)
    return jsonify(**file_resource)


@fichiers.route('/fichiers', methods=['POST'])
@requires_auth(roles='Observateur')
def fichier_create():
    payload = get_payload()
    # Check for mandatory fields
    missing_fields = [f for f in ['titre', 'mime'] if f not in payload]
    if missing_fields:
        abort(422, {f: 'missing field' for f in missing_fields})
    titre = payload.pop('titre')
    mime = payload.pop('mime')
    multipart = payload.pop('multipart', False)
    # Remaining fields are unexpected
    if payload.keys():
        abort(422, {f: 'unknown field' for f in payload.keys()})
    payload = {
        'titre': titre,
        'mime': mime,
        'proprietaire': g.request_user['_id'],
        'disponible': False,
        's3_id': uuid.uuid4().hex,
        's3_upload_done': False
    }
    if multipart:
        return _s3_create_multipart(payload)
    else:
        return _s3_create_singlepart(payload)


def _s3_create_singlepart(payload):
    sign = _sign_request(verb='PUT', object_name=payload['s3_id'],
                         content_type=payload['mime'])
    # Insert the file representation in the files resource
    inserted = fichiers.insert(payload)
    # signed_request is not stored in the database but transfered once
    inserted['s3_signed_url'] = sign['signed_url']
    return jsonify(**inserted), 201


def _s3_create_multipart(payload):
    amz_headers = {'x-amz-meta-title': payload['titre']}
    amz_headers['Content-Type'] = payload['mime']
    sign = _sign_request(verb='POST', object_name=payload['s3_id'],
                         content_type=payload['mime'], sign_head='uploads')
    # Create the multipart object on s3 using the signed request
    r = requests.post(sign['signed_url'], headers={'Content-Type': payload.get('mime', '')})
    if r.status_code != 200:
        logging.error('S3 {} error {} : {}'.format(sign['signed_url'], r.status_code, r.text))
        abort(500, 'S3 has rejected file creation request')
    # Why AWS doesn't provide a JSON api ???
    payload['s3_upload_multipart_id'] = re.search('<UploadId>(.+)</UploadId>', r.text).group(1)
    inserted = fichiers.insert(payload)
    return jsonify(**inserted), 201


@fichiers.route('/fichiers/<objectid:file_id>/multipart', methods=['PUT'])
@requires_auth(roles='Observateur')
def fichier_multipart_continue(file_id):
    payload = get_payload()
    part_number = payload.pop('part_number', None)
    if payload:
        abort(422, {f: 'unknown field' for f in payload.keys()})
    if not part_number:
        abort(422, {'part_number': 'missing field'})
    file_resource = fichiers.get_resource(file_id)
    if file_resource['proprietaire'] != g.request_user['_id']:
        abort(403)
    if 's3_id' not in file_resource or 's3_upload_multipart_id' not in file_resource:
        abort(422, 'not a multipart')
    sign = _sign_request(verb='PUT', object_name=file_resource['s3_id'],
                         sign_head='partNumber={}&uploadId={}'.format(
                            part_number,
                            file_resource['s3_upload_multipart_id'])
                        )
    return jsonify(s3_signed_url=sign['signed_url'])


@fichiers.route('/fichiers/<objectid:file_id>', methods=['DELETE'])
@requires_auth(roles='Observateur')
def fichier_delete(file_id):
    file_resource = fichiers.get_resource(file_id)
    if file_resource['proprietaire'] != g.request_user['_id']:
        abort(403)
    if 's3_id' not in file_resource or file_resource.get('s3_upload_done', False):
        abort(422, 'cannot cancel file once upload is done')
    if 's3_upload_multipart_id' in file_resource:
        # Destroy the unfinished file on S3
        sign = _sign_request(verb='DELETE', object_name=file_resource['s3_id'],
                             sign_head='uploadId=' + file_resource['s3_upload_multipart_id'])
        r = requests.delete(sign['signed_url'])
        if r.status_code != 204:
            logging.error('S3 {} error {} : {}'.format(sign['signed_url'], r.status_code, r.text))
            abort(500, 'S3 has rejected file creation request')
    fichiers.remove({'_id': file_resource['_id']})
    return jsonify(), 204


@fichiers.route('/fichiers/<objectid:file_id>', methods=['POST'])
@requires_auth(roles='Observateur')
def fichier_upload_done(file_id):
    file_resource = fichiers.get_resource(file_id)
    if file_resource['proprietaire'] != g.request_user['_id']:
        abort(403)
    if 's3_id' not in file_resource or file_resource.get('s3_upload_done', False):
        abort(422, 'upload is already done')
    if 's3_upload_multipart_id' in file_resource:
        # Finalize the file on S3
        payload = get_payload()
        if 'parts' not in payload:
            abort(422, 'missing field parts')
        file_resource = fichiers.get_resource(file_id)
        if 's3_id' not in file_resource or 's3_upload_multipart_id' not in file_resource:
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
        sign = _sign_request(verb='POST', object_name=file_resource['s3_id'],
                             content_type=content_type,
                             sign_head='uploadId='+file_resource['s3_upload_multipart_id']
                            )
        r = requests.post(sign['signed_url'],
                         headers={'Content-Type': content_type},
                         data=xml_body)
        if r.status_code != 200:
            logging.error('Completing {} error {} : {}'.format(
                sign['signed_url'], r.status_code, r.text))
            abort(500, 'Error with S3')
    # Finally update the resource status
    result = fichiers.update(file_id, {'s3_upload_done': True,
                                       'disponible': True})
    return jsonify(**result)


@fichiers.route('/fichiers/<objectid:file_id>/acces', methods=['GET'])
@requires_auth(roles='Observateur')
def s3_access_file(file_id):
    redirection = request.args.get('redirection', False)
    file_resource = fichiers.get_resource(file_id)
    _check_access_rights(file_resource)
    if 's3_id' not in file_resource or not file_resource.get('s3_upload_done', False):
        abort(410, 'file is not available')
    object_name = file_resource['s3_id']
    sign = _sign_request(verb='GET', object_name=object_name)
    if redirection:
        return redirect(sign['signed_url'], code=302)
    else:
        return jsonify(s3_signed_url=sign['signed_url'])
