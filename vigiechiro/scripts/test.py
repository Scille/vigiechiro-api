from .celery import app
from .. import settings

from pymongo import MongoClient


db = MongoClient(settings.MONGO_HOST, settings.MONGO_PORT)[
    settings.MONGO_DBNAME]


@app.task
def add(x, y):
    db.add.insert({'x': x, 'y': y, 'result': x + y})
    return x + y
