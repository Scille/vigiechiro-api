#! /bin/sh

. ./venv/bin/activate
./bin/init_db.py
PARAMS="$@"
if [ "$PARAMS" = "" ]
then
	py.test tests
else
	py.test $@
fi