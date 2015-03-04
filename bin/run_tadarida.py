#! /usr/bin/env python3

import logging; logging.basicConfig(level=logging.INFO)
import sys
from vigiechiro.scripts import tadarida


USAGE = 'usage : {} [d|c] [now|delay]'.format(sys.argv[0])


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) > 1 and sys.argv[1] in ['d', 'c']:
        args = iter(sys.argv)
        _ = next(args)
        script = next(args)
        timing = next(args, 'delay')
        if timing == 'delay':
            runner = lambda f: f.delay()
        elif timing == 'now':
            runner = lambda f: f()
        else:
            raise SystemExit(USAGE)
        if script == 'c':
            runner(tadarida.run_tadarida_c)
        else:
            runner(tadarida.run_tadarida_d)
    else:
        raise SystemExit(USAGE)
