from celery import Celery
from .. import settings


app = Celery('tasks', broker=settings.CELERY_BROKER_URL)


if __name__ == '__main__':
    app.start()
