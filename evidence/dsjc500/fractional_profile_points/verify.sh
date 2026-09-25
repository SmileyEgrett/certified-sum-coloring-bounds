#!/usr/bin/env bash
# Replay only the fixed DSJC500 continuous-point data identified by this package.
set -euo pipefail
export LC_ALL=C OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

if [[ $# -ne 1 ]]; then
    printf 'usage: %s NEW_EXTERNAL_WORK_DIRECTORY\n' "$0" >&2
    exit 2
fi
package=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
repository=$(CDPATH= cd -- "$package/../../.." && pwd -P)
work=$(realpath -m -- "$1")
case "$work/" in
    "$repository/"*) printf 'Work directory must be outside the checkout.\n' >&2; exit 2 ;;
esac
if [[ -e "$work" || -L "$work" ]]; then
    printf 'Work directory already exists: %s\n' "$work" >&2
    exit 2
fi
graph="$package/../dsjc500_integrated/data/DSJC500.9.col"
census="$package/../dsjc500_integrated/results/census/unresolved_cells.csv"
if [[ ! -f "$graph" ]]; then
    printf 'Missing DSJC500 graph; run scripts/fetch_graphs.sh from the repository root.\n' >&2
    exit 1
fi

# Check identities before creating work products or invoking a compiler.
(cd "$package" && sha256sum --check --strict SHA256SUMS)
verify_identity() {
    local expected=$1 file=$2 name=$3
    if ! printf '%s  %s\n' "$expected" "$file" | sha256sum --check --status; then
        printf 'INPUT_IDENTITY_FAIL: %s\n' "$name" >&2
        exit 1
    fi
}
verify_identity 95276841dffcde7c04de2fc1ae8e43b6c7b84173b4a9646b1cc6b392a3bd7b39 "$graph" graph
verify_identity 60f50a2de470d7fe6925d9b327cecc017def5a346723fc011b2817f9ada3e27f "$census" census
verify_identity 95758a2d7144dbc84c3a032237ccef0a4cc554d9385e7d4e2cb4d98fd372c19c "$package/certificates/reconstruction.json" reconstruction
verify_identity 25e14e3725e7629f4edce87dcb60848755edf5109ad8fc7fb1574d423cdaea5b "$package/certificates/fractional_lp/P5E_fractional_exact.json" P5E
verify_identity 9e3f7e8d3d2e70c00bbb9ac4fcce230829690f60cc2fdb12a5dd3a6087391285 "$package/certificates/fractional_lp/P5F_fractional_exact.json" P5F
verify_identity 187ea34d08ebc1d4840cf11240656f7bc836572273735ef36aece92b6967e147 "$package/certificates/fractional_lp/P7F_fractional_exact.json" P7F

mkdir -p -- "$(dirname -- "$work")"
mkdir -- "$work"
compiler=${CXX:-g++}
printf 'Compiler: %s\n' "$compiler" > "$work/compile.log"
if "$compiler" -std=c++20 -O2 -Wall -Wextra -Wpedantic \
    "$package/checks/check_endpoint_points.cpp" -o "$work/check_endpoint_points" \
    -lcrypto >> "$work/compile.log" 2>&1; then
    printf '0\n' > "$work/compile.exit"
else
    code=$?
    printf '%s\n' "$code" > "$work/compile.exit"
    cat "$work/compile.log" >&2
    exit "$code"
fi
if "$work/check_endpoint_points" "$graph" \
    "$package/certificates/fractional_lp" "$census" > "$work/replay.log" 2>&1; then
    printf '0\n' > "$work/replay.exit"
else
    code=$?
    printf '%s\n' "$code" > "$work/replay.exit"
    cat "$work/replay.log" >&2
    exit "$code"
fi
cat "$work/replay.log"
if ! grep -Fxq 'DSJC500_CURRENT_ENDPOINT_POINTS_PASS' "$work/replay.log"; then
    printf 'Missing endpoint completion marker.\n' >&2
    exit 1
fi
printf 'DSJC500_ENDPOINT_REPLAY_PASS\n'
