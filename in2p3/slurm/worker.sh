#!/bin/bash

. $VIGIECHIRO_DIR/init.env

python $VIGIECHIRO_DIR/vigiechiro-api/bin/queuer.py consume next_job
