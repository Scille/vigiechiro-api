#! /bin/bash

JOB_NAME="cq-$VIGIECHIRO_ENV_NAME"

# Move to the log folder before submitting the job to indicate where
# the stdout/stderr logs should end up
pushd $VIGIECHIRO_DIR/$VIGIECHIRO_ENV_NAME-logs

# --export option provides $VIGIECHIRO_DIR to the job process
# --job-name=$JOB_NAME seems broken, hence we must set this by using envvar
SBATCH_JOB_NAME=$JOB_NAME sbatch $VIGIECHIRO_DIR/slurm/check_queue.sh --export=VIGIECHIRO_DIR

popd
