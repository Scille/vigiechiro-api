web: ./bin/newrelic_bootstrap.sh gunicorn vigiechiro:app --log-file -
# web: gunicorn vigiechiro:app --log-file -
# web: python3 run_tornado.py
# web: uwsgi --http-socket localhost:$PORT -w vigiechiro:app
# web: waitress-serve --port $PORT vigiechiro:app

worker: ./bin/celery.sh -l info --concurrency=1
