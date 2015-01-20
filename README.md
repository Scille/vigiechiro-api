[ ![Codeship Status for Scille/vigiechiro-api](https://codeship.com/projects/87dc08b0-669d-0132-08ef-6acde1e9bce1/status?branch=master)](https://codeship.com/projects/52883)
# Vigie Chiro #

Projet vigiechiro du Museum national d'histoire naturelle

Partie API (backend)

## Install
```
# mongodb debian http://docs.mongodb.org/manual/tutorial/install-mongodb-on-debian/
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv 7F0CEB10
echo 'deb http://downloads-distro.mongodb.org/repo/debian-sysvinit dist 10gen' | sudo tee /etc/apt/sources.list.d/mongodb.list

# mongodb ubuntu http://docs.mongodb.org/manual/tutorial/install-mongodb-on-ubuntu/
sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 7F0CEB10
echo 'deb http://downloads-distro.mongodb.org/repo/ubuntu-upstart dist 10gen' | sudo tee /etc/apt/sources.list.d/mongodb.list
```

sudo apt-get update
sudo apt-get install -y mongodb-org
sudo apt-get install redis-server

sudo service mongod start
sudo service redis-server start

virtualenv venv
. ./venv/bin/activate
pip install -e .

./runserver.py
```

## Run tests
```
py.test tests
```

## Authentification

Pour configurer l'authentification via Oauth, les variables d'environnement suivante doivent être configurées
 - `GOOGLE_API_KEY` & `GOOGLE_API_SECRET` pour Google
 - `GITHUB_API_KEY` & `GITHUB_API_SECRET` pour Github
 - `FACEBOOK_API_KEY` & `FACEBOOK_API_SECRET` pour Facebook

Pour émuler l'authentification, `DEV_FAKE_AUTH` peut être mis à `true`
