from .celery import celery_app
from .. import settings

from pymongo import MongoClient


db = MongoClient(host=settings.get_mongo_uri())[
    settings.MONGO_DBNAME]


@celery_app.task
def add(x, y):
    db.add.insert({'x': x, 'y': y, 'result': x + y})
    return x + y
