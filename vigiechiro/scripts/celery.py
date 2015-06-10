from celery import Celery
from .. import settings


celery_app = Celery('tasks', broker=settings.CELERY_BROKER_URL,
                    include=['vigiechiro.scripts.task_tadarida_c',
                             'vigiechiro.scripts.task_tadarida_d',
                             'vigiechiro.scripts.task_participation'])


if __name__ == '__main__':
    import logging; logging.basicConfig(level=logging.INFO)
    celery_app.start()
