[ ![Codeship Status for Scille/vigiechiro-api](https://codeship.com/projects/87dc08b0-669d-0132-08ef-6acde1e9bce1/status?branch=master)](https://codeship.com/projects/52883)
# Vigie Chiro #

Projet vigiechiro du Museum national d'histoire naturelle

Partie API (backend)

## Install
```
sudo apt-get install mongodb
sudo apt-get install redis

virtualenv venv
. ./venv/bin/activate
export SECRET_KEY=xxx
export FRONTEND_DOMAIN='http://www.lvh.me:9000'
pip install -e .
cd vigiechiro && ./run.py
```

## Run tests
```
py.test tests
```
