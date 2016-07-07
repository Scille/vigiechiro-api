# Simple&custom message queue to play nice with in2p3 infrastructure

from flask import current_app
from pymongo import ASCENDING
from datetime import datetime
from traceback import format_exc


class QueuerError(Exception):
    pass


class QueuerBadTaskError(QueuerError):
    pass


class Queuer:
    def __init__(self, collection_name):
        self._collection_name = collection_name
        self._collection = None
        self.registered_tasks = {}

    def register_task(self, task):
        assert task.name not in self.registered_tasks
        self.registered_tasks[task.name] = task

    @property
    def collection(self):
        if not self._collection:
            self._collection = current_app.data.db[self._collection_name]
        return self._collection    

    def submit_job(self, task, *args, **kwargs):
        assert task in self.registered_tasks
        return self.collection.insert({'name': task, 'args': args, 'kwargs': kwargs,
                                       'submitted': datetime.utcnow(), 'status': 'READY'})

    def get_pending_jobs(self):
        return self.collection.find({'status': 'READY'}).sort([('submitted', ASCENDING)])

    def execute_next_job(self):
        while True:
            cursor = self.get_pending_jobs()
            if cursor.count() == 0:
                raise QueuerError('No task to execute')
            else:
                try:
                    return self.execute_job(cursor[0]['_id'])
                except QueuerBadTaskError:
                    # Task has been taken by somebody else
                    continue

    def execute_job(self, job_id):
        # First try to reserve the task
        ret = self.collection.update({'_id': job_id, 'status': 'READY'},
            {'$set': {'status': 'RESERVED', 'reserved_at': datetime.utcnow()}})
        if ret['n'] != 1:
            raise RuntimeError('Error trying to reserve the task %s: %s' % (job_id, ret))
        elif ret['nModified'] == 0:
            raise QueuerBadTaskError("Task %s doesn't exist or already taken" % job_id)
        job = self.collection.find_one({'_id': job_id})
        assert job['name'] in self.registered_tasks
        task = self.registered_tasks[job['name']]
        try:
            ret = task(*job['args'], **job['kwargs'])
        except:
            print('Error executing job %s:\n%s' % (job_id, format_exc()))
            self.collection.update(
                {'_id': job_id},
                {'$set': {'status': 'ERROR', 'errored_at': datetime.utcnow(), 'error': format_exc()}}
            )
        else:
            self.collection.update(
                {'_id': job_id},
                {'$set': {'status': 'DONE', 'done_at': datetime.utcnow()}}
            )
        return ret


queuer = Queuer('queuer_jobs')


class Task:
    def __init__(self, function):
        self.function = function
        self.name = function.__name__

    def delay(self, *args, **kwargs):
        """Register the function as a job and returns job id
        """
        return queuer.submit_job(self.name, *args, **kwargs)

    def __call__(self, *args, **kwargs):
        """Call the function synchronously
        """
        return self.function(*args, **kwargs)


def task(f):
    """Decorator to allow a function to be queued as job
    """
    t = Task(f)
    queuer.register_task(t)
    return t
