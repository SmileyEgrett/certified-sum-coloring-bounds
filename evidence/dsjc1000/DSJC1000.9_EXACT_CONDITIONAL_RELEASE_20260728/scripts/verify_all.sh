#!/usr/bin/env bash
set -euo pipefail
root=${1:-.}
python3 "$root/scripts/verify_release.py" --release-root "$root"
python3 "$root/scripts/test_malformed_certificates.py" --release-root "$root"
