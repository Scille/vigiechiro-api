from celery import Celery
from functools import wraps

from .. import settings


celery_app = Celery('tasks', broker=settings.CELERY_BROKER_URL,
                    include=['vigiechiro.scripts.task_tadarida_c',
                             'vigiechiro.scripts.task_tadarida_d',
                             'vigiechiro.scripts.task_participation'])
# http://celery.readthedocs.org/en/latest/userguide/optimizing.html#reserve-one-task-at-a-time
celery_app.conf.CELERYD_PREFETCH_MULTIPLIER = 1
celery_app.conf.CELERYD_CONCURRENCY = 1
celery_app.conf.CELERY_ACKS_LATE = True


# TODO: find a cleaner fix...
# Currently, hirefire doesn't take into account the currently processed
# tasks. Hence it can kill a worker during the process of a job.
# To solve that, we spawn a dummy task and disable worker parallelism
@celery_app.task
def dummy_keep_alive():
    print('dummy_keep_alive')

_celery_app_task = celery_app.task
def keep_alive_task(*args, **kwargs):
    cls = _celery_app_task(*args, **kwargs)
    delay = cls.delay
    @wraps(cls.delay)
    def delay_wrapper(*args, **kwargs):
        ret = delay(*args, **kwargs)
        dummy_keep_alive.delay()
        return ret
    cls.delay = delay_wrapper
    return cls
celery_app.task = keep_alive_task


if __name__ == '__main__':
    import logging; logging.basicConfig(level=logging.INFO)
    celery_app.start()
