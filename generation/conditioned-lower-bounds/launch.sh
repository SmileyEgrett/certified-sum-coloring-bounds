#!/usr/bin/env bash
set -euo pipefail
base=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
cpu=${1:?usage: launch.sh CPU [run.py arguments]}
shift
[[ "$cpu" =~ ^[0-9]+$ ]] || { echo 'CPU must be one logical CPU number' >&2; exit 2; }
python=${PYTHON:-python3}
unset PYTHONOPTIMIZE PYTHONPATH PYTHONHOME
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 BLIS_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 LC_ALL=C
exec systemd-run --user --scope --quiet \
    -p MemoryMax=4294967296 -p MemorySwapMax=0 -p TasksMax=64 \
    taskset -c "$cpu" "$python" "$base/run.py" "$@"
