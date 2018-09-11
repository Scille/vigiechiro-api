#! /bin/bash

. ./venv/bin/activate
./bin/init_db.py reset
PARAMS="$@"
if [ "$PARAMS" = "" ]
then
	py.test tests
else
	py.test $@
fi
