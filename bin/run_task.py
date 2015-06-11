#! /usr/bin/env python3

import logging; logging.basicConfig(level=logging.INFO)
import sys
from vigiechiro.scripts import (
    tadaridaD, tadaridaC, tadaridaC_batch, tadaridaC_batch_watcher,
    participation_generate_bilan)


USAGE = 'usage : {} [d|c|c_batch|c_batch_watcher|bilan] [now|delay] <resource_id>'.format(sys.argv[0])


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) == 3 and sys.argv[2] in ['now', 'delay']:
        _, script, timing = sys.argv
        if timing == 'delay':
            runner = lambda f: f.delay()
        else:
            runner = lambda f: f()
        if script == 'c_batch':
            raise SystemExit(runner(tadaridaC_batch))
        elif script ==  'c_batch_watcher':
            raise SystemExit(runner(tadaridaC_batch_watcher))
    elif len(sys.argv) == 4 and sys.argv[1] in ['d', 'c', 'bilan'] and sys.argv[2] in ['now', 'delay']:
        _, script, timing, fichier_id = sys.argv
        if timing == 'delay':
            runner = lambda f: f.delay(fichier_id)
        else:
            runner = lambda f: f(fichier_id)
        if script == 'c':
            raise SystemExit(runner(tadaridaC))
        elif script == 'd':
            raise SystemExit(runner(tadaridaD))
        else:
            raise SystemExit(runner(participation_generate_bilan))
    raise SystemExit(USAGE)
