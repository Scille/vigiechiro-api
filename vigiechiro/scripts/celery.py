from celery import Celery
from .. import settings


celery_app = Celery('tasks', broker=settings.CELERY_BROKER_URL,
                    include=['vigiechiro.scripts.tadarida'])


if __name__ == '__main__':
    celery_app.start()
