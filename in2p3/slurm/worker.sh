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

python $VIGIECHIRO_DIR/vigiechiro-api/bin/queuer.py consume next_job
