#! /bin/sh

DIR=`dirname $0`/..

cd $DIR && celery -A vigiechiro.scripts.celery worker $@
