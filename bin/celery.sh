#! /bin/sh

OLD_DIR=`pwd`
DIR=`dirname $0`/..

cd $DIR
celery -A ..vigiechiro.scripts.celery worker $@
cd $OLD_DIR
