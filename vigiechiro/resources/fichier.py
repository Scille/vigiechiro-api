"""
File upload module
Basic usage : the client POST a file then the serveur send back a link
to the resource representing the file.
In case of very large files, another way is to make a first POST with no
payload but a manifest containing the size of the file in order to first
cut the file then send the parts using PATCH with informations on the part's
size and position.
"""

import base64
import urllib
import os
import json
import time
import hmac
from hashlib import sha1
from flask import request, jsonify, abort, redirect, current_app
import uuid
import bson
import eve.auth
import eve.render
import eve.methods
from eve.methods.post import post_internal

from .resource import Resource, relation


class Fichier(Resource):
    RESOURCE_NAME = 'fichiers'
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

    def __init__(self):
        super().__init__()
        # Settings module imports resources, cannot do global import here
        from vigiechiro import settings
        self.AWS_KEY = settings.AWS_KEY
        self.AWS_SECRET = settings.AWS_SECRET
        self.S3_BUCKET = settings.S3_BUCKET

        @self.route('/s3', methods=['POST'], allowed_roles=['Observateur'])
        def sign_s3():
            return self._sign_s3()

        @self.route('/<file_id>/action/acces', methods=['GET'])
        def archive(file_id):
            return self._access_s3(file_id)

        @self.callback
        def on_replace(item, original):
            self._check_rights(original, item)

        @self.callback
        def on_fetched_item(response):
            self._check_rights(response)

        @self.callback
        def on_update(updates, original):
            self._check_rights(original, updates)

    def _check_rights(self, file_, updates=None):
        """Admin can do everything, owner can read/write, other users
           can only read if the data is not private
        """
        if current_app.g.request_user['role'] == 'Administrateur':
            return
        is_owner = file_['proprietaire'] == current_app.g.request_user['_id']
        if updates:
            if not is_owner:
                abort(403)
            if set(updates.keys()) & self.CONST_FIELDS:
                abort(
                    403,
                    'not allowed to alter field(s) {}'.format(const_fields))
        else:
            if file_.get('prive', False) and not is_owner:
                abort(403)

    def _access_s3(self, file_id):
        """Redirect to a signed url to get the file back from S3"""
        files_db = current_app.data.driver.db[self.RESOURCE_NAME]
        try:
            file_id = bson.ObjectId(file_id)
        except bson.errors.InvalidId:
            abort('Invalid ObjectId {}'.format(file_id), code=400)
        file_ = files_db.find_one({'_id': file_id})
        if not file_:
            abort(404)
        self._check_rights(file_)
        object_name = file_['nom']
        expires = int(time.time() + 10)
        get_request = "GET\n\n\n{}\n/{}/{}".format(expires,
                                                   self.S3_BUCKET, object_name)
        signature = base64.encodestring(
            hmac.new(
                self.AWS_SECRET.encode(),
                get_request.encode(),
                sha1).digest())
        signature = urllib.parse.quote_plus(signature.strip())
        url = 'https://{}.s3.amazonaws.com/{}'.format(
            self.S3_BUCKET,
            object_name)
        return redirect('{}?AWSAccessKeyId={}&Expires={}&Signature={}'.format(
                        url, self.AWS_KEY, expires, signature), code=302)

    def _sign_s3(self):
        """Return a signed url to let the user upload a file to s3"""
        object_name = uuid.uuid4().hex
        # object_name = request.args.get('s3_object_name')
        payload = request.json
        mime_type = payload.get('mime', '')
        expires = int(time.time() + 10)
        # TODO : change public-read is case of non-public file
        amz_headers = "x-amz-acl:public-read"
        put_request = "PUT\n\n{}\n{}\n{}\n/{}/{}".format(
            mime_type, expires, amz_headers, self.S3_BUCKET, object_name)
        signature = base64.encodestring(
            hmac.new(
                self.AWS_SECRET.encode(),
                put_request.encode(),
                sha1).digest())
        signature = urllib.parse.quote_plus(signature.strip())
        url = 'https://{}.s3.amazonaws.com/{}'.format(
            self.S3_BUCKET,
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
                self.AWS_KEY,
                expires,
                signature)
        return eve.render.send_response('fichiers', response)
