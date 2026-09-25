#!/usr/bin/env bash
# Check the exact graph-free distribution; Git history is a separate boundary.
set -euo pipefail
export LC_ALL=C
root=$(realpath -- "${1:-.}")
manifest="$root/PUBLIC_MANIFEST.sha256"
[[ -f $manifest && ! -L $manifest ]] || { echo 'missing regular public manifest' >&2; exit 1; }
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
previous=''
while IFS= read -r line; do
 [[ $line =~ ^([0-9a-f]{64})\ \ ([A-Za-z0-9_./+-]+)$ ]] || { echo 'malformed public manifest row' >&2; exit 1; }
 path=${BASH_REMATCH[2]}
 [[ $path != /* && $path != */ && $path != *//* && $path != PUBLIC_MANIFEST.sha256 ]] || { echo 'unsafe or self-referential public manifest path' >&2; exit 1; }
 case "/$path/" in */../*|*/./*|*/.git/*) echo 'unsafe public manifest path' >&2; exit 1;; esac
 [[ -z $previous || $path > $previous ]] || { echo 'duplicate or unsorted public manifest path' >&2; exit 1; }
 previous=$path
 printf '%s\n' "$path"
done < "$manifest" > "$scratch/expected"
(
 cd "$root"
 find . -path ./.git -prune -o -print0 > "$scratch/walk"
 while IFS= read -r -d '' path; do
  path=${path#./}
  [[ $path != . ]] || continue
  if [[ -L $path ]]; then echo "symlink rejected: $path" >&2; exit 1; fi
  [[ ! -d $path ]] || continue
  [[ -f $path ]] || { echo "special file rejected: $path" >&2; exit 1; }
  [[ $path != PUBLIC_MANIFEST.sha256 ]] || continue
  printf '%s\n' "$path"
 done < "$scratch/walk"
) > "$scratch/actual.unsorted"
sort "$scratch/actual.unsorted" > "$scratch/actual"
cmp "$scratch/expected" "$scratch/actual" || { echo 'public file set mismatch' >&2; exit 1; }
(cd "$root" && sha256sum --check --strict --quiet PUBLIC_MANIFEST.sha256)
printf 'PUBLIC_DISTRIBUTION_VERIFIED files=%s\n' "$(wc -l < "$scratch/expected")"
