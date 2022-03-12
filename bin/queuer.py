#! /usr/bin/env python3

from sys import argv
from bson import ObjectId
from pprint import pprint
from functools import wraps

from vigiechiro.scripts import queuer, participation_generate_bilan, process_participation, participation_generate_observations_csv


USAGE = """usage:
{cmd} submit [participation|bilan|observations_csv] <partication_id>    Submit a task as a job for asynchronous execution
{cmd} exec [participation|bilan|observations_csv] <partication_id>      Synchronous execution of the given task
{cmd} consume [<job_id>|next_job]                      Synchronous execution of the given job
{cmd} pendings                                         Return number of pending jobs
{cmd} info <job_id>                                    Return info on a given job
""".format(cmd=argv[0])


def get_task(shortname):
    if shortname == 'participation':
        return process_participation
    elif shortname == 'bilan':
        return participation_generate_bilan
    elif shortname == "observations_csv":
        return participation_generate_observations_csv
    else:
        raise RuntimeError('Unknown task %s' % shortname)

def context(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        from vigiechiro.app import app as flask_app
        with flask_app.app_context():
            return f(*args, **kwargs)

    return wrapper


@context
def pending_jobs_count():
    return queuer.get_pending_jobs_count()


@context
def pending_jobs_info():
    return list(queuer.get_pending_jobs()[:20])


@context
def get_job_status(job_id):
    return queuer.collection.find_one({'_id': job_id})


@context
def submit_job(task, *args, **kwargs):
    return task.delay(*args, **kwargs)


def main():
    if len(argv) > 1:
        if argv[1] == 'pendings' and len(argv) == 2:
            count = pending_jobs_count()
            print(count)
            raise SystemExit(1 if count == 0 else 0)
        elif argv[1] == 'info':
            if len(argv) == 2:
                data = pending_jobs_info()
                pprint(data)
                raise SystemExit(0)
            elif len(argv) == 3:
                data = get_job_status(ObjectId(argv[2]))
                if data:
                    pprint(data)
                    raise SystemExit(0)
        elif argv[1] in ('submit', 'exec') and len(argv) == 4:
            task = get_task(argv[2])
            if task:
                participation_id = ObjectId(argv[3])
                if argv[1] == 'submit':
                    job_id = submit_job(task, participation_id)
                    print('Submitted job %s' % job_id)
                    return
                else:
                    return context(task)(participation_id)
        elif argv[1] == 'consume' and len(argv) == 3:
            if argv[2] == 'next_job':
                return context(queuer.execute_next_job)()
            else:
                job_id = ObjectId(argv[2])
                return context(queuer.execute_job)(job_id)
    raise SystemExit(USAGE)


if __name__ == '__main__':
    main()
