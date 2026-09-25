#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C OMP_NUM_THREADS=1
if [[ $# -ne 2 ]]; then
    printf 'usage: %s PREFLIGHT_BINARY NEW_EXTERNAL_TEST_DIRECTORY\n' "$0" >&2; exit 2
fi
binary=$(realpath -e -- "$1")
scripts=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
repository=$(CDPATH= cd -- "$scripts/.." && pwd -P)
work=$(realpath -m -- "$2")
case "$work/" in "$repository/"*) printf 'Test directory must be external.\n' >&2; exit 2 ;; esac
[[ ! -e "$work" && ! -L "$work" ]] || { printf 'Test directory already exists.\n' >&2; exit 2; }
mkdir -p "$work"
expect_status() {
    local name=$1 expected=$2 code=0; shift 2
    "$@" > "$work/$name.log" 2>&1 || code=$?
    printf '%s\n' "$code" > "$work/$name.exit"
    [[ $code -eq $expected ]] || { cat "$work/$name.log" >&2; printf 'FAIL %s expected %s got %s\n' "$name" "$expected" "$code" >&2; exit 1; }
    printf 'CONTROL %s exit=%s PASS\n' "$name" "$code"
}
mkdir -p "$work/good/parts"
cat > "$work/good/paper.tex" <<'TEX'
\documentclass{article}
\begin{document}
\input{parts/section}
\bibliography{refs}
\end{document}
TEX
cat > "$work/good/parts/section.tex" <<'TEX'
\label{sec:good}\ref{sec:good}\cite{used}
% \input{missing-comment}\cite{missing-comment}
\verb|\input{missing-verb}|
\begin{lstlisting}
\input{missing-listing}
\end{lstlisting}
TEX
printf '@article{used, title={Used}, year={2026}}\n' > "$work/good/refs.bib"
printf '\\cite{inactive}\n' > "$work/good/inactive.tex"
printf '@article{inactive, title={Inactive}}\n' > "$work/good/inactive.bib"
expect_status good 0 "$binary" "$work/good/paper.tex" --export "$work/good export"
[[ ! -e "$work/good export/inactive.tex" && ! -e "$work/good export/inactive.bib" ]]
expect_status existing-export 2 "$binary" "$work/good/paper.tex" --export "$work/good export"
cmp "$work/good/refs.bib" "$work/good export/refs.bib"
for name in unused missing-key duplicate-key duplicate-label undefined-ref wildcard missing-input dynamic-input cycle repeated-input private-comment; do
    dir="$work/$name"; cp -a "$work/good" "$dir"
    case "$name" in
        unused) printf '@article{inactive, title={Unused}}\n' >> "$dir/refs.bib" ;;
        missing-key) printf '\\cite{absent}\n' >> "$dir/parts/section.tex" ;;
        duplicate-key) printf '@article{used, title={Duplicate}}\n' >> "$dir/refs.bib" ;;
        duplicate-label) printf '\\label{sec:good}\n' >> "$dir/parts/section.tex" ;;
        undefined-ref) printf '\\eqref{absent}\n' >> "$dir/parts/section.tex" ;;
        wildcard) printf '\\nocite{*}\n' >> "$dir/parts/section.tex" ;;
        missing-input) printf '\\input{absent}\n' >> "$dir/parts/section.tex" ;;
        dynamic-input) printf '\\input{\\chosen}\n' >> "$dir/parts/section.tex" ;;
        cycle) printf '\\input{paper}\n' >> "$dir/parts/section.tex" ;;
        repeated-input)
            awk '{if ($0=="\\bibliography{refs}") print "\\input{parts/section}"; print}' \
                "$dir/paper.tex" > "$dir/repeated.tex"
            mv "$dir/repeated.tex" "$dir/paper.tex" ;;
        private-comment) printf '%% /%s/fixture\n' tmp >> "$dir/parts/section.tex" ;;
    esac
    expect_status "$name" 1 "$binary" "$dir/paper.tex" --export "$work/$name export"
    [[ ! -e "$work/$name export" ]]
    case "$name" in
        unused) diagnostic='unused bibliography key inactive' ;;
        missing-key) diagnostic='missing bibliography key absent' ;;
        duplicate-key) diagnostic='duplicate bibliography key used' ;;
        duplicate-label|repeated-input) diagnostic='duplicate label sec:good' ;;
        undefined-ref) diagnostic='undefined reference absent' ;;
        wildcard) diagnostic='wildcard citation/reference prohibited' ;;
        missing-input) diagnostic='missing dependency absent' ;;
        dynamic-input) diagnostic='unsupported dynamic/control syntax: dependency' ;;
        cycle) diagnostic='cyclic TeX dependency' ;;
        private-comment) diagnostic='private/local path marker' ;;
    esac
    grep -Fq "$diagnostic" "$work/$name.log"
done
mkdir "$work/parity"
cat > "$work/parity/paper.tex" <<'TEX'
\documentclass{article}
\begin{document}
Escaped percent \% \cite{used}.
Line break \\% \cite{fake}
\bibliography{refs}
\end{document}
TEX
cp "$work/good/refs.bib" "$work/parity/refs.bib"
expect_status comment-parity 0 "$binary" "$work/parity/paper.tex"
cat > "$work/fail-compiler" <<'COMPILER'
#!/usr/bin/env bash
exit 42
COMPILER
chmod +x "$work/fail-compiler"
expect_status wrapper-compiler 42 env CXX="$work/fail-compiler" bash "$scripts/check_manuscript.sh" \
    "$work/good/paper.tex" "$work/compiler output"
[[ ! -e "$work/compiler output/active-source" ]]
expect_status wrapper-existing 2 bash "$scripts/check_manuscript.sh" "$work/good/paper.tex" "$work/good export"
expect_status wrapper-args 2 bash "$scripts/check_manuscript.sh" "$work/good/paper.tex"
cat > "$work/stub-compiler" <<'COMPILER'
#!/usr/bin/env bash
set -euo pipefail
out=
while [[ $# -gt 0 ]]; do
    if [[ $1 == -o ]]; then out=$2; shift 2; else shift; fi
done
[[ -n "$out" ]]
cat > "$out" <<'CHILD'
#!/usr/bin/env bash
if [[ $FAKE_MODE == nonzero ]]; then
    printf 'MANUSCRIPT_PREFLIGHT=PASS\n'
    exit 7
fi
exit 0
CHILD
chmod +x "$out"
COMPILER
chmod +x "$work/stub-compiler"
expect_status wrapper-nonzero 7 env CXX="$work/stub-compiler" FAKE_MODE=nonzero \
    bash "$scripts/check_manuscript.sh" "$work/good/paper.tex" "$work/nonzero output"
expect_status wrapper-no-marker 1 env CXX="$work/stub-compiler" FAKE_MODE=empty \
    bash "$scripts/check_manuscript.sh" "$work/good/paper.tex" "$work/empty output"
printf 'MANUSCRIPT_PREFLIGHT_REGRESSION_PASS\n'
