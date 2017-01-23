#! /usr/bin/env python3

import os
import sys
import requests
import logging


# Keep config here to make this script standalone
AUTH = ("token_for_test_only", None)
BACKEND_DOMAIN = "https://vigiechiro-test.herokuapp.com"


def iter_participation_files(participation_id, **kwargs):
    max_results = kwargs.pop('max_results', 100)
    current_page = 1
    while True:
        params = {'max_results': max_results, 'page': current_page}
        params.update(kwargs)
        r = requests.get(BACKEND_DOMAIN + '/participations/%s/pieces_jointes' % participation_id,
                         params=params, auth=AUTH, timeout=90)
        if r.status_code != 200:
            logging.error('Retrieving participation {} error {} : {}'.format(
                participation_id, r.status_code, r.text))
            return 1
        data = r.json()
        for fichier_data in data['_items']:
            yield fichier_data
        total = data['_meta']['total']
        max_current = current_page * max_results
        if total < max_current:
            break
        print('Dowloaded %s/%s' % (max_current, total))
        current_page += 1


def get_participation_files(participation_id):
    wdir = './participation_%s_fichiers' % participation_id
    os.mkdir(wdir)
    for i, fichier_data in enumerate(iter_participation_files(participation_id, ta=True)):
        r = requests.get(BACKEND_DOMAIN + '/fichiers/%s/acces' % fichier_data['_id'],
                         params={'redirection': True}, stream=True, auth=AUTH, , timeout=90)
        data_path = '/'.join((wdir, fichier_data['titre']))
        with open(data_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)
                    f.flush()
        if r.status_code != 200:
            logger.error('Cannot get back file %s (%s) : error %s' %
                (fichier_data['_id'], fichier_data['titre'], r.status_code))
            return 1
    print(' Done')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit("usage: %s <participtaion_id>" %
                         os.path.basename(sys.argv[0]))
    get_participation_files(sys.argv[1])
