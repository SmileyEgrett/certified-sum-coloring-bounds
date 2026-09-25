#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")" && pwd -P)
if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "usage: $0 /path/to/DSJC250.9.col [work-directory]" >&2
  exit 64
fi

if [[ $# -eq 2 ]]; then
  work=$(realpath -m "$2")
  [[ ! -e "$work" ]]
  mkdir -p "$work"
  cleanup=false
else
  work=$(mktemp -d)
  cleanup=true
fi
if $cleanup; then trap 'rm -rf "$work"' EXIT; fi

package="$work/package"
"$root/materialize.sh" "$1" "$package"
mkdir -p "$work/check"
g++ -std=c++20 -O2 -Wall -Wextra -Wpedantic \
  "$package/source_snapshot/check.cpp" -o "$work/check/check"

for run in mip01 mip02; do
  "$work/check/check" \
    "$package/input/DSJC250.9.col" \
    "$package/results/generated/stable_sets.tsv" \
    "$package/results/generated/master.mps" \
    "$package/results/$run/solve.columns.tsv" \
    "$work/check/$run" | tee "$work/check/$run.stdout"
  cmp "$work/check/$run.coloring" "$package/results/$run/verified.coloring"
  cmp "$work/check/$run.selected.tsv" "$package/results/$run/verified.selected.tsv"
  grep -Fx 'status=Optimal' "$package/results/$run/solve.summary.txt" >/dev/null
  grep -Fx 'objective=8276.9999999999982' "$package/results/$run/solve.summary.txt" >/dev/null
  grep -Fx 'mip_dual_bound=8276.9999999999982' "$package/results/$run/solve.summary.txt" >/dev/null
  grep -Fx 'mip_gap=0' "$package/results/$run/solve.summary.txt" >/dev/null
  grep -Fx 'mip_nodes=1601' "$package/results/$run/solve.summary.txt" >/dev/null
  grep -Fx 'simplex_iterations=278786' "$package/results/$run/solve.summary.txt" >/dev/null
done

cmp "$package/results/mip01/solve.columns.tsv" \
    "$package/results/mip02/solve.columns.tsv"
cmp "$root/EXPECTED_CENSUS.tsv" "$package/results/generated/census.tsv"

echo 'DSJC250.9 DIRECT INTEGER MASTER STATIC VERIFICATION PASSED'
