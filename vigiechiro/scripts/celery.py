from celery import Celery
from .. import settings


celery_app = Celery('tasks', broker=settings.CELERY_BROKER_URL)


if __name__ == '__main__':
    celery_app.start()
