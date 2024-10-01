#!/bin/bash

# We use conda to provide an isolated environment for Python & R.
#
# To activate environments, conda requires some configuration in
# our environment variable. This is normally handled by `conda init`
# (which typically put stuff in `~/.bashrc`).
#
# However in slurm the job executes its script (i.e. *this* file)
# with a pristine shell so conda complains we must call `conda init`
# before doing a `conda activate` :/
#
# So the solution is simply to do the work of `conda init` by sourcing
# `$MINICONDA3_DIR/etc/profile.d/conda.sh`

# Conda command is located on e.g. `/pbs/throng/mnhn/cl9/miniconda3/condabin/conda`
# We want to source `/pbs/throng/mnhn/cl9/miniconda3/etc/profile.d/conda.sh`
CONDA_CMD_PATH=`which conda`
MINICONDA3_DIR=`dirname \`dirname $CONDA_CMD_PATH\``
COND_INIT_PATH=$MINICONDA3_DIR/etc/profile.d/conda.sh
. $COND_INIT_PATH

# Now we can load the configuration (and, among other things, activate the conda env)
. $VIGIECHIRO_DIR/init.env

SELF_SCRIPT_PATH=$VIGIECHIRO_DIR/slurm/check_queue.sh
WORKER_SCRIPT_PATH=$VIGIECHIRO_DIR/slurm/worker.sh
WORKER_JOB_NAME="w-$VIGIECHIRO_ENV_NAME"
# Set max time (i.e. `--time` param) to 2 days, basically we have:
# - 4% of jobs >5h
# - 1% of jobs >12h
# - Longest observed so far is 54h
WORKER_JOB_OPTIONS="--time=2-00:00:00 --cpus-per-task=1 --mem=32GB --constraint el9 --job-name=$WORKER_JOB_NAME"

function get_scheduled_workers() {
    echo "import subprocess
user_name = '$(whoami)'
job_name = '${WORKER_JOB_NAME}'
cmd = f'squeue --states=PD --name={job_name} --user={user_name}'
out = subprocess.check_output(cmd.split()).decode()
print(len([l for l in out.splitlines()[1:] if l.strip()]))
" | python
}

# Run the script for 60 * 120 == 2 hours
# This is much lower than the default maximum time (i.e. 7 days)
for i in `seq 120`
do
    PENDINGS=`python $VIGIECHIRO_DIR/vigiechiro-api/bin/queuer.py pendings`
    SCHEDULED_WORKERS=`get_scheduled_workers`
    NEEDED_TO_START=$(($PENDINGS - $SCHEDULED_WORKERS))
    if ( [ "$NEEDED_TO_START" -gt 0 ] )
    then
        printf "[$(date)] $PENDINGS pending jobs, starting worker\n"
        # Move to the log folder before submitting the job to indicate where
        # the stdout/stderr logs should end up
        LOG_FOLDER="$VIGIECHIRO_DIR/$VIGIECHIRO_ENV_NAME-logs/$(date +%Y-%m)-worker"
        mkdir -p $LOG_FOLDER
        pushd $LOG_FOLDER
        # --job-name=$WORKER_JOB_NAME seems broken, hence we must set this by using envvar
        SBATCH_JOB_NAME=$WORKER_JOB_NAME sbatch $WORKER_JOB_OPTIONS $WORKER_SCRIPT_PATH
        popd
    else
        printf "[$(date)] no pending jobs\n"
    fi
    # Remove core dump given they flood very fast the home directory
    rm -fv $HOME/vigiechiro-prod/Tadarida-C/tadaridaC_src/core.*
    sleep 60
done

# Then reload itself to prevent being killed by quotas
# note: Couldn't use $(readlink -f $0) given slurm copy the
# script in a temp folder before running it
echo "[$(date)] restarting daemon"

# --export option provides $VIGIECHIRO_DIR to the job process
# --job-name=$SLURM_JOB_NAME seems broken, hence we must set this by using envvar
# `--mem` `--time` and `--cpus-per-task` are rough estimates considering
# `check_queue.sh` is a single small script restarting itself every 2h.
#
# /!\ This command must be similar than the one in `start_slurm_check_queue.sh` /!\
SBATCH_JOB_NAME=$JOB_NAME sbatch \
    --export=VIGIECHIRO_DIR \
    --mem=100MB \
    --time=0-04:00:00 \
    --constraint el9 \
    --cpus-per-task=1 \
    $VIGIECHIRO_DIR/slurm/check_queue.sh
