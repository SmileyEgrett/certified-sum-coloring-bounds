#!/usr/bin/env bash
# Literal active-source preflight; supported syntax and limits are documented.
set -euo pipefail
export LC_ALL=C OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
if [[ $# -ne 2 ]]; then
    printf 'usage: %s PAPER_TEX NEW_EXTERNAL_WORK_DIRECTORY\n' "$0" >&2
    exit 2
fi
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
repository=$(CDPATH= cd -- "$script_dir/.." && pwd -P)
paper=$(realpath -e -- "$1")
work=$(realpath -m -- "$2")
case "$work/" in
    "$repository/"*) printf 'Work directory must be outside the checkout.\n' >&2; exit 2 ;;
esac
if [[ -e "$work" || -L "$work" ]]; then
    printf 'Work directory already exists: %s\n' "$work" >&2
    exit 2
fi
mkdir -p -- "$(dirname -- "$work")"
mkdir -- "$work"
compiler=${CXX:-g++}
if "$compiler" -std=c++20 -O2 -Wall -Wextra -Wpedantic \
    "$script_dir/manuscript_preflight.cpp" -o "$work/manuscript_preflight" \
    > "$work/compile.log" 2>&1; then
    printf '0\n' > "$work/compile.exit"
else
    code=$?
    printf '%s\n' "$code" > "$work/compile.exit"
    cat "$work/compile.log" >&2
    exit "$code"
fi
if "$work/manuscript_preflight" "$paper" --export "$work/active-source" \
    > "$work/preflight.log" 2>&1; then
    printf '0\n' > "$work/preflight.exit"
else
    code=$?
    printf '%s\n' "$code" > "$work/preflight.exit"
    cat "$work/preflight.log" >&2
    exit "$code"
fi
cat "$work/preflight.log"
grep -Fxq 'MANUSCRIPT_PREFLIGHT=PASS' "$work/preflight.log"
mkdir "$work/tmp"
if TMPDIR="$work/tmp" bash "$script_dir/check_bibliography.sh" "$work/active-source" \
    > "$work/bibliography.log" 2>&1; then
    printf '0\n' > "$work/bibliography.exit"
else
    code=$?
    printf '%s\n' "$code" > "$work/bibliography.exit"
    cat "$work/bibliography.log" >&2
    exit "$code"
fi
cat "$work/bibliography.log"
grep -Fxq 'BIBLIOGRAPHY_USAGE_CHECK=PASS' "$work/bibliography.log"
printf 'MANUSCRIPT_CHECK_PASS\n'
