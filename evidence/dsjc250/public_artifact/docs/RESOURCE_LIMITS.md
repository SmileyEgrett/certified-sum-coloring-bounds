# Resource and immutability policy

Replay wrappers default to a 180-second CPU limit and a 2-GiB virtual-memory limit per checker where the host shell supports `ulimit -t` and `ulimit -v`. Override them with `CPU_LIMIT_SECONDS` and `VIRTUAL_MEMORY_KB`. The checkers also enforce graph dimensions, stable/profile enumeration node limits, JSON/decompressed-proof byte limits, proof-record limits, and descriptor-declared column counts.

The shipped proof does not launch a solver or generate a new tree. Output JSON and logs must be written outside the release tree. `PYTHONDONTWRITEBYTECODE=1` suppresses bytecode caches. The release manifest rejects symbolic links, missing files, extra files, and changed bytes. The second checker receives the graph only in a disposable staged copy. A before/after manifest comparison is the release test for proof-critical immutability.
