#! /usr/bin/env python3

import logging; logging.basicConfig(level=logging.INFO)
import sys
from vigiechiro.scripts import participation_generate_bilan, process_participation

USAGE = 'usage : {} [participation|bilan] [now|delay] <participation_id>'.format(sys.argv[0])


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) == 4 and sys.argv[1] in ['participation', 'bilan'] and sys.argv[2] in ['now', 'delay']:
        _, script, timing, participation_id = sys.argv
        if timing == 'delay':
            runner = lambda f: f.delay(participation_id)
        else:
            runner = lambda f: f(participation_id)
        if script == 'participation':
            raise SystemExit(runner(process_participation))
        else:
            raise SystemExit(runner(participation_generate_bilan))
    raise SystemExit(USAGE)
