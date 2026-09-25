#!/usr/bin/env bash
set -euo pipefail

# Fetch benchmark graphs from the COLOR03/COLOR04 host without storing their
# bytes in Git. The frozen evidence manifests are checked after installation.
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
CACHE="$ROOT/graphs"
mkdir -p "$CACHE"

verify_hash() {
    local expected="$1" path="$2"
    printf '%s  %s\n' "$expected" "$path" | sha256sum --check --status
}

fetch_graph() {
    local name="$1" url="$2" expected="$3"
    local dest="$CACHE/$name" tmp
    if [[ -e "$dest" ]]; then
        if ! verify_hash "$expected" "$dest"; then
            printf 'Wrong hash for existing graph: %s\n' "$dest" >&2
            return 1
        fi
        printf 'Verified cached %s\n' "$name"
        return
    fi
    tmp="$(mktemp "$CACHE/$name.part.XXXXXX")"
    if ! curl --fail --location --silent --show-error --retry 3 --max-time 180 \
        --output "$tmp" "$url"; then
        rm -f -- "$tmp"
        return 1
    fi
    if ! verify_hash "$expected" "$tmp"; then
        printf 'Downloaded graph has wrong hash: %s\n' "$url" >&2
        rm -f -- "$tmp"
        return 1
    fi
    mv -- "$tmp" "$dest"
    printf 'Fetched and verified %s\n' "$name"
}

install_graph() {
    local name="$1" expected="$2" relative_dest="$3"
    local source="$CACHE/$name"
    local dest="$ROOT/$relative_dest"
    if [[ -e "$dest" ]]; then
        if ! verify_hash "$expected" "$dest"; then
            printf 'Wrong hash for existing evidence graph: %s\n' "$dest" >&2
            return 1
        fi
        return
    fi
    install -D -m 0644 "$source" "$dest"
    verify_hash "$expected" "$dest"
}

hash250=1b90f811e4d44f8937075865790b845e986b08b9da53caea57b2adf1c57383e7
hash500=95276841dffcde7c04de2fc1ae8e43b6c7b84173b4a9646b1cc6b392a3bd7b39
hash1000=b73613d4ec2eb988ff124258ebff728a2c08e603c778c7547a15f320a79f61c6
hash2000=aa4b1d7df7f9c1afbf8c9f35fcf5bdfc6370fd27db5c9f3fd5409dfd0d164f16

fetch_graph DSJC250.9.col \
    https://mat.tepper.cmu.edu/COLOR03/INSTANCES/DSJC250.9.col \
    "$hash250"
fetch_graph DSJC500.9.col \
    https://mat.tepper.cmu.edu/COLOR04/INSTANCES/DSJC500.9.col \
    "$hash500"
fetch_graph DSJC1000.9.col \
    https://mat.tepper.cmu.edu/COLOR04/INSTANCES/DSJC1000.9.col \
    "$hash1000"
fetch_graph C2000.9.col \
    https://mat.tepper.cmu.edu/COLOR04/INSTANCES/C2000.9.clq \
    "$hash2000"

install_graph DSJC500.9.col "$hash500" \
    evidence/dsjc500/dsjc500_integrated/data/DSJC500.9.col
install_graph DSJC500.9.col "$hash500" \
    evidence/dsjc500/dsjc500_integrated/baseline/dsjc5009-open-exact-investigation/data/DSJC500.9.col
install_graph DSJC1000.9.col "$hash1000" \
    evidence/dsjc1000/DSJC1000.9_EXACT_CONDITIONAL_RELEASE_20260728/instance/DSJC1000.9.col
install_graph C2000.9.col "$hash2000" \
    evidence/c2000_9/C2000.9.col
install_graph C2000.9.col "$hash2000" \
    evidence/c2000_9/c2000_fractional_exact_certificate_20260913T122045Z/input/C2000.9.col

printf 'All benchmark graph bytes match the frozen source hashes.\n'
