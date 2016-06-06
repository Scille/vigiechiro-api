#! /usr/bin/env python

from os import environ
from time import sleep
import argparse
from subprocess import call
import requests


QSUB_JOB_NAME = 'qsub_worker-%s' % environ['VIGIECHIRO_ENV_NAME']
QSUB_WORKER_SCRIPT = environ['VIGIECHIRO_DIR'] + '/qsub_worker.sh'


def get_queue_status():
    r = requests.get(environ["HIREFIRE_POLLING_URL"])
    quantity = r.json()[0]['quantity']
    return quantity if isinstance(quantity, int) else 0


def submit_qsub():
    call('qsub ' + QSUB_WORKER_SCRIPT, shell=True)


def delete_qsub():
    call('qdel ' + QSUB_JOB_NAME, shell=True)


def is_qsub_started():
    return call('qstat -j %s 1>/dev/null' % QSUB_JOB_NAME, shell=True) == 0


def f_trigger_qsub(f):

    def wrapper(*args, **kwargs):
        j = f(*args, **kwargs)
        if j:
            if is_qsub_started():
                print('Worker already in place (%s messages in queue)' % j)
            else:
                print('Trigger qsub (%s jobs in queue)' % j)
                submit_qsub()
        elif is_qsub_started():
            print('No more messages in queue, delete qsub job')
            delete_qsub()
            
        return j

    return wrapper


def f_display(f):

    def wrapper(*args, **kwargs):
        j = f(*args, **kwargs)
        print('%s jobs in queue' % j)
        return j

    return wrapper


def f_run_in_loop(f, sleep_time):

    def wrapper(*args, **kwargs):
        try:
            while True:
                j = f(*args, **kwargs)
                sleep(sleep_time)
        except KeyboardInterrupt:
            print('Keyboard interruption, exiting.')
            return j

    return wrapper


def main():
    parser = argparse.ArgumentParser(description='Trigger queue worker')
    parser.add_argument('--poll', '-p', type=int, default=0,
                        help='Interval in second to do the polling (default: no polling)')
    parser.add_argument('--trigger', '-t', action='store_true',
                        help='Submit/delete the qsub job according to pending messages state (default: false)')
    args = parser.parse_args()

    function = get_queue_status

    if args.trigger:
        function = f_trigger_qsub(function)
    else:
        function = f_display(function)

    if args.poll:
        function = f_run_in_loop(function, args.poll)

    j = function()

    if j:
        raise SystemExit(1)
    else:
        raise SystemExit(0)


if __name__ == '__main__':
    main()

