#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd -P)
source "$root/scripts/_limits.sh"
if [[ $# -ne 1 ]]; then echo "usage: $0 /path/to/DSJC250.9.col" >&2; exit 64; fi
graph=$(realpath "$1"); scratch=$(mktemp -d -t dsjc2509-mutations.XXXXXX); trap 'rm -rf "$scratch"' EXIT
python3 "$root/scripts/stage_independent.py" "$graph" "$scratch/checker" >/dev/null
python3 "$scratch/checker/scripts/run_mutation_tests.py"
