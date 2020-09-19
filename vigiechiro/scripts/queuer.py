# Simple&custom message queue to play nice with in2p3 infrastructure

import logging
logger = logging.getLogger(__name__)
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
        res = self.collection.insert_one({'name': task, 'args': args, 'kwargs': kwargs,
                                          'submitted': datetime.utcnow(), 'status': 'READY'})
        return res.inserted_id

    def get_pending_jobs_count(self):
        return self.collection.count_documents({'status': 'READY'})

    def get_pending_jobs(self):
        return self.collection.find({'status': 'READY'}).sort([('submitted', ASCENDING)])

    def execute_next_job(self):
        while True:
            next_job = list(self.get_pending_jobs()[:1])
            if not next_job:
                raise QueuerError('No task to execute')
            else:
                next_job = next_job[0]
                try:
                    return self.execute_job(next_job['_id'])
                except QueuerBadTaskError:
                    # Task has been taken by somebody else
                    continue

    def execute_job(self, job_id):
        # First try to reserve the task
        ret = self.collection.update_one({'_id': job_id, 'status': 'READY'},
            {'$set': {'status': 'RESERVED', 'reserved_at': datetime.utcnow()}})
        if ret.matched_count != 1:
            raise RuntimeError('Error trying to reserve the task %s: %s' % (job_id, ret))
        elif ret.modified_count == 0:
            raise QueuerBadTaskError("Task %s doesn't exist or already taken" % job_id)
        job = self.collection.find_one({'_id': job_id})
        assert job['name'] in self.registered_tasks
        task = self.registered_tasks[job['name']]
        logger.info('Executing job %s' % job)
        try:
            ret = task(*job['args'], **job['kwargs'])
        except:
            print('Error executing job %s:\n%s' % (job_id, format_exc()))
            self.collection.update_one(
                {'_id': job_id},
                {'$set': {'status': 'ERROR', 'errored_at': datetime.utcnow(), 'error': format_exc()}}
            )
        else:
            self.collection.update_one(
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

    def delay_singleton(self, *args, **kwargs):
        """Register as a job if the function with thoses arguments
        has is not already is database.
        """
        if not queuer.collection.find_one(
                {'name': self.name, 'args': args, 'kwargs': kwargs, 'status': 'READY'},
                projection={}):
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
