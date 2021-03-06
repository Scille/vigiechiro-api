#! /bin/env python3

from os import environ
from os.path import dirname, abspath
from sys import argv


WORK_DIR = dirname(abspath(__file__))
TARGET_DIR = argv[1] if len(argv) > 1 else '.'

kwargs = {
    'env_name': environ['VIGIECHIRO_ENV_NAME'],
    'vigiechiro_dir': environ['VIGIECHIRO_DIR']
}


for qsub in ('qsub_worker', 'qsub_check_queue'):
    with open(WORK_DIR + '/' + qsub + '.tmpl') as fd:
        content = fd.read().format(**kwargs).split('\n')
    content = [content[0], "\n### Autogenerated, don't change me !!! ###"] + content[1:]
    with open(TARGET_DIR + '/' + qsub + '.sh', 'w') as fd:
        fd.write('\n'.join(content))
