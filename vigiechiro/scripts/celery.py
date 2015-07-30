from celery import Celery
from .. import settings


celery_app = Celery('tasks', broker=settings.CELERY_BROKER_URL,
                    include=['vigiechiro.scripts.task_tadarida_c',
                             'vigiechiro.scripts.task_tadarida_d',
                             'vigiechiro.scripts.task_participation'])
# http://celery.readthedocs.org/en/latest/userguide/optimizing.html#reserve-one-task-at-a-time
celery_app.conf.CELERYD_PREFETCH_MULTIPLIER = 1
celery_app.conf.CELERYD_CONCURRENCY = 1
celery_app.conf.CELERY_ACKS_LATE = True

if __name__ == '__main__':
    import logging; logging.basicConfig(level=logging.INFO)
    celery_app.start()
