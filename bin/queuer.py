#! /usr/bin/env python3

import logging; logging.basicConfig(level=logging.INFO)
import argparse
from sys import argv
from bson import ObjectId
from pprint import pprint
import json

from vigiechiro.scripts import participation_generate_bilan, process_participation
from vigiechiro.resources import queuer
from vigiechiro.app import app as flask_app


USAGE = """usage:
{cmd} submit [participation|bilan] <partication_id>    Submit a task as a job for asynchronous execution
{cmd} exec [participation|bilan] <partication_id>      Synchronous execution of the given task
{cmd} consume [<job_id>|next_job]                      Synchronous execution of the given job
{cmd} info                                             Return number of pending jobs""".format(cmd=argv[0])


def get_task(shortname):
    if shortname == 'participation':
        return process_participation
    elif shortname == 'bilan':
        return participation_generate_bilan
    else:
        raise RuntimeError('Unknown task %s' % shortname)


def main():
    if len(argv) > 1:
        with flask_app.app_context():
            if argv[1] == 'info':
                if len(argv) == 2:
                    count = queuer.get_pending_jobs().count()
                    print("pending jobs: %s" % count)
                    raise SystemExit(1 if count == 0 else 0)
                elif len(argv) == 3:
                    data = queuer.collection.find_one({'_id': ObjectId(argv[2])})
                    if data:
                        pprint(data)
                        raise SystemExit(0)
                    else:
                        raise SystemExit('Unknown job %s' % argv[2])
            elif argv[1] in ('submit', 'exec') and len(argv) == 4:
                task = get_task(argv[2])
                if task:
                    participation_id = ObjectId(argv[3])
                    if argv[1] == 'submit':
                        job_id = task.delay(participation_id)
                        print('Submitted job %s' % job_id)
                        return
                    else:
                        return task(partication_id)
            elif argv[1] == 'consume' and len(argv) == 3:
                if argv[2] == 'next_job':
                    return queuer.execute_next_job()
                else:
                    job_id = ObjectId(argv[2])
                    return queuer.execute_job(job_id)
    raise SystemExit(USAGE)


if __name__ == '__main__':
    main()
