#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")" && pwd -P)
archive="$root/DSJC250.9_DIRECT_MSC_EXACT_20260918T213200Z_PUBLIC.zip"
package=DSJC250.9_DIRECT_MSC_EXACT_20260918T213200Z_PUBLIC
expected_graph=1b90f811e4d44f8937075865790b845e986b08b9da53caea57b2adf1c57383e7

if [[ $# -ne 2 ]]; then
  echo "usage: $0 /path/to/DSJC250.9.col output-directory" >&2
  exit 64
fi

graph=$(realpath "$1")
destination=$(realpath -m "$2")
if [[ -e "$destination" ]]; then
  echo "output already exists: $destination" >&2
  exit 65
fi

printf '%s  %s\n' "$expected_graph" "$graph" | sha256sum --check --quiet
(cd "$root" && sha256sum --check --quiet SHA256SUMS)

scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
unzip -q "$archive" -d "$scratch"
chmod -R u+w "$scratch/$package"
install -D -m 0644 "$graph" "$scratch/$package/input/DSJC250.9.col"
(cd "$scratch/$package" && sha256sum --check --quiet SHA256SUMS)
mkdir -p "$(dirname "$destination")"
mv "$scratch/$package" "$destination"
echo "MATERIALIZED $destination"
