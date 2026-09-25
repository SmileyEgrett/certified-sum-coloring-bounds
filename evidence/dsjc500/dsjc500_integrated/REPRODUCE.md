# Exact replay

Use the [shared replay prerequisites](../../../REPRODUCE.md), including
Python 3.10 or later. After running `scripts/fetch_graphs.sh` from the paper
repository root, enter this directory and run:

```sh
./scripts/replay.sh
```

The Python standard-library replay checks the complete runtime manifest
before consuming proof data. It verifies the initial 29,785/1,269-cell stage,
the P2/P4 residual bounds, all 17 conditional trees and 30 mappings, the
fixed-coloring certificate, census, splitting frontier and supporting normals.

Success requires exit zero and the final marker
`DSJC500.9 INTEGRATED DELTA CHECK PASSED`. The reconstructed interval is
[29,791,29,848], with 1,165 unresolved cells through 29,847.

The same entry point can be invoked directly as
`PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify_all.py --root .`.
No certificate-generation software or numerical solver is needed.
