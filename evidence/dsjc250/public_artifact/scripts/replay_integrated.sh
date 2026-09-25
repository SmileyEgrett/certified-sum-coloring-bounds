#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd -P)
source "$root/scripts/_limits.sh"
if [[ $# -lt 1 || $# -gt 2 ]]; then echo "usage: $0 /path/to/DSJC250.9.col [json-output]" >&2; exit 64; fi
graph=$(realpath "$1"); out=${2:-}
python3 "$root/scripts/check_graph.py" "$graph" >/dev/null
cmd=(python3 "$root/integrated_checker/scripts/exact_mscp_conditional_verify.py" --graph "$graph" --campaign "$root/integrated_checker/instances/dsjc2509/conditional/campaign.properties" --stable-mode materialized)
[[ -z "$out" ]] || cmd+=(--json-out "$out")
exec "${cmd[@]}"
