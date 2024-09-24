#! /bin/bash

JOB_NAME="cq-$VIGIECHIRO_ENV_NAME"

# Move to the log folder before submitting the job to indicate where
# the stdout/stderr logs should end up
LOG_FOLDER="$VIGIECHIRO_DIR/$VIGIECHIRO_ENV_NAME-logs/check_queue"
mkdir -p $LOG_FOLDER
pushd $LOG_FOLDER

# --export option provides $VIGIECHIRO_DIR to the job process
# --job-name=$JOB_NAME seems broken, hence we must set this by using envvar
# `--mem` `--time` and `--cpus-per-task` are rough estimates considering
# `check_queue.sh` is a single small script restarting itself every 10h.
SBATCH_JOB_NAME=$JOB_NAME sbatch \
    --export=VIGIECHIRO_DIR \
    --mem=100MB \
    --time=0-06:00:00 \
    --constraint el9 \
    --cpus-per-task=1 \
    $VIGIECHIRO_DIR/slurm/check_queue.sh

popd
