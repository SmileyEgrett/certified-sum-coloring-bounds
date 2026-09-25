# Benchmark graph provenance

The paper's proof objects are bound to exact DIMACS graph bytes. This
repository does not commit or redistribute those graph files. Run
./scripts/fetch_graphs.sh from a checkout to download them from the CMU
COLOR03/COLOR04 instance host, check SHA-256, and install the copies expected
by the frozen evidence manifests. A wrong cached or downloaded file causes the
script to fail.

| Graph | Official download | SHA-256 of downloaded bytes |
|---|---|---|
| DSJC250.9 | https://mat.tepper.cmu.edu/COLOR03/INSTANCES/DSJC250.9.col | 1b90f811e4d44f8937075865790b845e986b08b9da53caea57b2adf1c57383e7 |
| DSJC500.9 | https://mat.tepper.cmu.edu/COLOR04/INSTANCES/DSJC500.9.col | 95276841dffcde7c04de2fc1ae8e43b6c7b84173b4a9646b1cc6b392a3bd7b39 |
| DSJC1000.9 | https://mat.tepper.cmu.edu/COLOR04/INSTANCES/DSJC1000.9.col | b73613d4ec2eb988ff124258ebff728a2c08e603c778c7547a15f320a79f61c6 |
| C2000.9 | https://mat.tepper.cmu.edu/COLOR04/INSTANCES/C2000.9.clq | aa4b1d7df7f9c1afbf8c9f35fcf5bdfc6370fd27db5c9f3fd5409dfd0d164f16 |

The C2000.9 upstream filename ends in .clq. Its bytes are identical to the
historically supplied C2000.9.col used by this paper; only the local filename
differs. DSJC500.9 and C2000.9 are each required at two evidence-package
paths, so the fetch script installs a checked copy in both locations.
DSJC250.9 is kept under the ignored graphs/ cache and passed explicitly to
its checker.

These four URLs were downloaded and compared byte-for-byte with the frozen
working graph files on 21 September 2026. This document asserts source
identity, not permission to redistribute the upstream files. The repository
therefore records hashes and retrieval instructions rather than graph bytes.
