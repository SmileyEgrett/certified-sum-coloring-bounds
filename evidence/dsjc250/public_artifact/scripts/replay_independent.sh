#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd -P)
source "$root/scripts/_limits.sh"
if [[ $# -lt 1 || $# -gt 2 ]]; then echo "usage: $0 /path/to/DSJC250.9.col [json-output]" >&2; exit 64; fi
graph=$(realpath "$1"); out=${2:-}; scratch=$(mktemp -d -t dsjc2509-independent.XXXXXX); trap 'rm -rf "$scratch"' EXIT
python3 "$root/scripts/stage_independent.py" "$graph" "$scratch/checker" >/dev/null
cmd=(python3 "$scratch/checker/scripts/verify.py" --root "$scratch/checker")
[[ -z "$out" ]] || cmd+=(--json-out "$out")
"${cmd[@]}"
