from .celery import app
from .hirefire import hirefire
from .. import settings

from pymongo import MongoClient


db = MongoClient(host=settings.get_mongo_uri())[
    settings.MONGO_DBNAME]


@app.task
def add(x, y):
    db.add.insert({'x': x, 'y': y, 'result': x + y})
    return x + y
