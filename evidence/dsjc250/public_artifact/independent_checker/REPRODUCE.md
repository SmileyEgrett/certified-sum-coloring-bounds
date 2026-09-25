# Checking this source tree

Use the [artifact replay prerequisites](../docs/REPLAY.md). From the artifact root, run `./scripts/replay_independent.sh /external/DSJC250.9.col [output.json]`. The wrapper validates the graph, stages this directory to scratch, adds the graph, regenerates the scratch manifest, and invokes `scripts/verify.py`. Do not run `scripts/verify.sh` directly in this source-only tree. Certificate regeneration is outside the release replay contract and is not required or claimed here.
