#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd -P)
if [[ $# -lt 1 || $# -gt 2 ]]; then echo "usage: $0 /path/to/DSJC250.9.col [output-directory]" >&2; exit 64; fi
graph=$(realpath "$1"); out=${2:-"$PWD/replay-output"}; mkdir -p "$out"
python3 "$root/scripts/verify_release_manifest.py" "$root"
python3 "$root/scripts/check_graph.py" "$graph" --json-out "$out/graph.json"
/usr/bin/time -v "$root/scripts/replay_integrated.sh" "$graph" "$out/integrated.json" >"$out/integrated.stdout" 2>"$out/integrated.stderr"
/usr/bin/time -v "$root/scripts/replay_independent.sh" "$graph" "$out/independent.json" >"$out/independent.stdout" 2>"$out/independent.stderr"
python3 "$root/profiles/enumerate_nested.py" --verify --output "$out/profiles.nested.csv" >"$out/profiles.nested.summary"
python3 "$root/profiles/enumerate_cumulative.py" --verify --output "$out/profiles.cumulative.csv" >"$out/profiles.cumulative.summary"
cmp "$out/profiles.nested.csv" "$out/profiles.cumulative.csv"
cmp "$out/profiles.nested.csv" "$root/profiles/threshold_profiles_6668.csv"
echo "ALL REPLAYS AND PROFILE REGENERATIONS PASSED"
