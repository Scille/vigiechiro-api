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
import json
import datetime
import urllib
import time
import logging
import hmac
from hashlib import sha1
import uuid
from flask import request, abort, current_app, g, redirect
import requests
import re

from .. import settings
from ..xin import Resource
from ..xin.tools import jsonify, abort
from ..xin.auth import requires_auth
from ..xin.schema import relation, choice
from ..xin.snippets import get_payload
from .utilisateurs import utilisateurs as utilisateurs_resource


ALLOWED_MIMES_PHOTOS = ['image/bmp', 'image/png', 'image/jpg', 'image/jpeg']
ALLOWED_MIMES_TA = ['application/ta', 'application/tac']
ALLOWED_MIMES_TC = ['application/tc', 'application/tcc']
ALLOWED_MIMES_WAV = ['audio/wav', 'audio/x-wav']


def _validate_donnee(context, donnee):
    if donnee['proprietaire'] != context.document.get('proprietaire', None):
        return 'fichier and donnee must have the same owner'


def _validate_participation(context, participation):
    if participation['observateur'] != context.document.get('proprietaire', None):
        return 'fichier and participation must have the same owner'


SCHEMA = {
    'titre': {'type': 'string', 'postonly': True, 'required': True},
    'mime': {'type': 'string', 'postonly': True, 'required': True},
    'proprietaire': relation('utilisateurs', postonly=True, required=True),
    'disponible': {'type': 'boolean'},
    's3_id': {'type': 'string', 'postonly': True, 'unique': True},
    's3_upload_multipart_id': {'type': 'string', 'postonly': True},
    'lien_protocole': relation('protocoles'),
    'lien_donnee': relation('donnees', validator=_validate_donnee),
    'lien_participation': relation('participations', validator=_validate_participation),
    '_async_process': {'type': 'string'}
}


fichiers = Resource('fichiers', __name__, schema=SCHEMA)


def delete_fichier_and_s3(fichier):
    if not isinstance(fichier, dict):
        fichier = fichiers.get_resource(fichier)
    # Destroy the unfinished file on S3
    if fichier.get('s3_upload_multipart_id', False):
        sign = _sign_request(verb='DELETE', object_name=fichier['s3_id'],
                             sign_head='uploadId=' + fichier['s3_upload_multipart_id'])
    else:
        sign = _sign_request(verb='DELETE', object_name=fichier['s3_id'])
    r = requests.delete(sign['signed_url'])
    if r.status_code != 204:
        logging.error('S3 {} error {} : {}'.format(sign['signed_url'], r.status_code, r.text))
        return r
    fichiers.remove({'_id': fichier['_id']})
    return None


def get_file_from_s3(fichier, data_path):
    object_name = fichier.get('s3_id')
    if not object_name:
        return None
    if not settings.DEV_FAKE_S3_URL:
        signed_url = _sign_request(verb='GET', object_name=object_name)['signed_url']
    else:
        signed_url = settings.DEV_FAKE_S3_URL + '/' + object_name
    r = requests.get(signed_url, stream=True)
    with open(data_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk: # filter out keep-alive new chunks
                f.write(chunk)
                f.flush()
    return r


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
    expires = kwargs.pop('expires', int(time.time() + 3600))
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


def _aws_sign(to_sign):
    if not isinstance(to_sign, bytes):
        to_sign = to_sign.encode('utf8')
    signature = base64.b64encode(hmac.new(
            current_app.config['AWS_SECRET_ACCESS_KEY'].encode(),
            base64.b64encode(to_sign),
            sha1).digest())
    return signature.strip().decode()


@fichiers.route('/fichiers/<objectid:fichier_id>', methods=['GET'])
@requires_auth(roles='Observateur')
def display_fichier(fichier_id):
    file_resource = fichiers.get_resource(fichier_id)
    _check_access_rights(file_resource)
    return file_resource


@fichiers.route('/fichiers', methods=['POST'])
@requires_auth(roles='Observateur')
def fichier_create():
    payload = get_payload()
    # Check for mandatory fields
    missing_fields = [f for f in ['titre', 'mime'] if f not in payload]
    if missing_fields:
        abort(422, {f: 'missing field' for f in missing_fields})
    titre = payload.pop('titre')
    if not re.match(r'^[a-zA-Z0-9_\-.]+$', titre):
        abort(422, {'titre': 'string contains forbidden characters'})
    mime = payload.pop('mime')
    multipart = payload.pop('multipart', False)
    lien_donnee = payload.pop('lien_donnee', None)
    lien_participation = payload.pop('lien_participation', None)
    lien_protocole = payload.pop('lien_protocole', None)
    async_process = payload.pop('_async_process', None)
    if g.request_user['role'] == 'Administrateur':
        proprietaire = payload.pop('proprietaire', g.request_user['_id'])
    else:
        proprietaire = g.request_user['_id']
    # Remaining fields are unexpected
    if payload.keys():
        abort(422, {f: 'unknown field' for f in payload.keys()})
    delay_work = None
    from .donnees import validate_donnee_name
    if mime in ALLOWED_MIMES_PHOTOS:
        path = 'photos/'
    elif mime in ALLOWED_MIMES_TA:
        path = 'ta/'
        if not validate_donnee_name(titre):
            abort(422, {'titre': 'invalid name ' + titre})
    elif mime in ALLOWED_MIMES_TC:
        path = 'tc/'
        if not validate_donnee_name(titre):
            abort(422, {'titre': 'invalid name ' + titre})
    elif mime in ALLOWED_MIMES_WAV:
        path = 'wav/'
        if not validate_donnee_name(titre):
            abort(422, {'titre': 'invalid name ' + titre})
    else:
        path = 'others/'
    payload = {
        'titre': titre,
        'mime': mime,
        'proprietaire': proprietaire,
        'disponible': False,
    }
    if async_process:
        payload['_async_process'] = async_process
    if lien_donnee:
        payload['lien_donnee'] = lien_donnee
    if lien_participation:
        payload['lien_participation'] = lien_participation
        payload['s3_id'] = "%spa%s/%s" % (path, lien_participation, titre)
    else:
        payload['s3_id'] = "%s%s" % (path, titre)
    if lien_protocole:
        payload['lien_protocole'] = lien_protocole
    if multipart:
        abort(422, {'errors': {'multipart': 'Multipart upload not supported'}})
    else:
        result = _s3_create_singlepart(payload)
        if not settings.DEV_FAKE_S3_URL:
            sign = _sign_request(verb='PUT', object_name=payload['s3_id'],
                                 content_type=payload['mime'])
            result[0]['s3_signed_url'] = sign['signed_url']
        else:
            result[0]['s3_signed_url'] = settings.DEV_FAKE_S3_URL + '/' + payload['s3_id']
    if delay_work:
        delay_work(result[0]['_id'])
    return result


def _s3_create_singlepart(payload):
    # Make sure no older&incomplete file is present
    fichiers.remove({'s3_id': payload['s3_id'], 'disponible': False})
    # Insert the file representation in the files resource
    inserted = fichiers.insert(payload)
    expiration = datetime.datetime.utcnow() + datetime.timedelta(seconds=3600)
    policy = json.dumps({
        "expiration": expiration.isoformat() + 'Z',
        "conditions": [
            {"acl": "private"},
            {"key": payload['s3_id']},
            {"bucket": current_app.config['AWS_S3_BUCKET']},
            {"Content-Encoding": "gzip"}
        ]
    })
    inserted['s3_policy'] = base64.b64encode(policy.encode('utf8')).decode()
    inserted['s3_signature'] = _aws_sign(policy)
    inserted['s3_aws_access_key_id'] = current_app.config['AWS_ACCESS_KEY_ID']
    return inserted, 201


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
    if not settings.DEV_FAKE_S3_URL:
        sign = _sign_request(verb='PUT', object_name=file_resource['s3_id'],
                             sign_head='partNumber={}&uploadId={}'.format(
                                part_number,
                                file_resource['s3_upload_multipart_id'])
                            )
    else:
        sign = {'signed_url': settings.DEV_FAKE_S3_URL}
    return {'s3_signed_url': sign['signed_url']}

@fichiers.route('/fichiers/<objectid:file_id>', methods=['DELETE'])
@requires_auth(roles='Observateur')
def fichier_delete(file_id):
    file_resource = fichiers.get_resource(file_id)
    if file_resource['proprietaire'] != g.request_user['_id']:
        abort(403)
    if 's3_id' not in file_resource or file_resource.get('disponible', False):
        abort(422, 'cannot cancel file once upload is done')
    if 's3_upload_multipart_id' in file_resource and not settings.DEV_FAKE_S3_URL:
        # Destroy the unfinished file on S3
        sign = _sign_request(verb='DELETE', object_name=file_resource['s3_id'],
                             sign_head='uploadId=' + file_resource['s3_upload_multipart_id'])
        r = requests.delete(sign['signed_url'])
        if r.status_code != 204:
            logging.error('S3 {} error {} : {}'.format(sign['signed_url'], r.status_code, r.text))
            abort(500, 'S3 has rejected file creation request')
    fichiers.remove({'_id': file_resource['_id']})
    return {}, 204


@fichiers.route('/fichiers/<objectid:file_id>', methods=['POST'])
@requires_auth(roles='Observateur')
def fichier_upload_done(file_id):
    file_resource = fichiers.get_resource(file_id)
    if (g.request_user['role'] != 'Administrateur' and
        file_resource['proprietaire'] != g.request_user['_id']):
        abort(403)
    if 's3_id' not in file_resource or file_resource.get('disponible', False):
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
        if not settings.DEV_FAKE_S3_URL:
            r = requests.post(sign['signed_url'],
                             headers={'Content-Type': content_type},
                             data=xml_body)
            if r.status_code != 200:
                logging.error('Completing {} error {} : {}'.format(
                    sign['signed_url'], r.status_code, r.text))
                abort(500, 'Error with S3')
    # Finally update the resource status
    result = fichiers.update(file_id, {'disponible': True})
    return result


@fichiers.route('/fichiers/<objectid:file_id>/acces', methods=['GET'])
@requires_auth(roles='Observateur')
def s3_access_file(file_id):
    redirection = request.args.get('redirection', False)
    file_resource = fichiers.get_resource(file_id)
    _check_access_rights(file_resource)
    if 's3_id' not in file_resource or not file_resource.get('disponible', False):
        abort(410, 'file is not available')
    object_name = file_resource['s3_id']
    if not settings.DEV_FAKE_S3_URL:
        sign = _sign_request(verb='GET', object_name=object_name)
    else:
        sign = {'signed_url': settings.DEV_FAKE_S3_URL + '/' + object_name}
    if redirection:
        return redirect(sign['signed_url'], code=302)
    else:
        return {'s3_signed_url': sign['signed_url']}
