#! /usr/bin/env python3

import logging; logging.basicConfig(level=logging.INFO)
import sys
from vigiechiro.scripts import tadaridaD, tadaridaC


USAGE = 'usage : {} [d|c] [now|delay] fichier_id'.format(sys.argv[0])


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) == 4 and sys.argv[1] in ['d', 'c'] and sys.argv[2] in ['now', 'delay']:
        _, script, timing, fichier_id = sys.argv
        if timing == 'delay':
            runner = lambda f: f.delay(fichier_id)
        else:
            runner = lambda f: f(fichier_id)
        if script == 'c':
            raise SystemExit(runner(tadaridaC))
        else:
            raise SystemExit(runner(tadaridaD))
    else:
        raise SystemExit(USAGE)
