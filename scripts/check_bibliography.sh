#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 /path/to/paper-directory" >&2
  exit 64
fi

paper_dir=$1
if [[ ! -d "$paper_dir" ]]; then
  echo "ERROR: paper directory does not exist: $paper_dir" >&2
  exit 66
fi

mapfile -d '' tex_files < <(find "$paper_dir" -type f -name '*.tex' -print0 | sort -z)
mapfile -d '' bib_files < <(find "$paper_dir" -type f -name '*.bib' -print0 | sort -z)

if [[ ${#tex_files[@]} -eq 0 ]]; then
  echo "ERROR: no TeX files found under $paper_dir" >&2
  exit 66
fi
if [[ ${#bib_files[@]} -eq 0 ]]; then
  echo "ERROR: no BibTeX files found under $paper_dir" >&2
  exit 66
fi

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

LC_ALL=C sed -nE \
  's/^[[:space:]]*@[[:alpha:]]+[[:space:]]*\{[[:space:]]*([^,[:space:]]+)[[:space:]]*,.*/\1/p' \
  "${bib_files[@]}" > "$work_dir/bib_keys_all"

LC_ALL=C sort "$work_dir/bib_keys_all" > "$work_dir/bib_keys_sorted"
LC_ALL=C uniq "$work_dir/bib_keys_sorted" > "$work_dir/bib_keys"
LC_ALL=C uniq -d "$work_dir/bib_keys_sorted" > "$work_dir/duplicate_keys"

# Read every active TeX source as a whole file, remove ordinary TeX comments,
# and extract keys from the complete family of commands whose names contain
# "cite" (cite, citep, citet, citeauthor, nocite, and variants).
LC_ALL=C perl -0777 -ne '
  s/(?<!\\)%[^\n]*//g;
  while (/\\[A-Za-z]*cite[A-Za-z]*(?:\s*\[[^\]]*\])*\s*\{([^}]*)\}/g) {
    for $key (split /,/, $1) {
      $key =~ s/^\s+|\s+$//g;
      print "$key\n" if length($key);
    }
  }
' "${tex_files[@]}" > "$work_dir/cited_keys_all"

if LC_ALL=C grep -Fxq '*' "$work_dir/cited_keys_all"; then
  echo 'ERROR: \nocite{*} masks unused bibliography entries; justify and audit it explicitly.' >&2
  exit 65
fi

LC_ALL=C sort -u "$work_dir/cited_keys_all" > "$work_dir/cited_keys"
LC_ALL=C comm -23 "$work_dir/bib_keys" "$work_dir/cited_keys" > "$work_dir/unused_keys"
LC_ALL=C comm -13 "$work_dir/bib_keys" "$work_dir/cited_keys" > "$work_dir/missing_keys"

bib_count=$(wc -l < "$work_dir/bib_keys")
cited_count=$(wc -l < "$work_dir/cited_keys")
unused_count=$(wc -l < "$work_dir/unused_keys")
missing_count=$(wc -l < "$work_dir/missing_keys")
duplicate_count=$(wc -l < "$work_dir/duplicate_keys")

echo "paper_dir=$paper_dir"
echo "bib_entries=$bib_count"
echo "cited_unique=$cited_count"
echo "unused_entries=$unused_count"
echo "missing_entries=$missing_count"
echo "duplicate_entries=$duplicate_count"

if [[ $unused_count -ne 0 ]]; then
  echo 'UNUSED:'
  sed 's/^/  /' "$work_dir/unused_keys"
fi
if [[ $missing_count -ne 0 ]]; then
  echo 'MISSING:'
  sed 's/^/  /' "$work_dir/missing_keys"
fi
if [[ $duplicate_count -ne 0 ]]; then
  echo 'DUPLICATE:'
  sed 's/^/  /' "$work_dir/duplicate_keys"
fi

if [[ $unused_count -ne 0 || $missing_count -ne 0 || $duplicate_count -ne 0 ]]; then
  echo 'BIBLIOGRAPHY_USAGE_CHECK=FAIL'
  exit 1
fi

echo 'BIBLIOGRAPHY_USAGE_CHECK=PASS'
