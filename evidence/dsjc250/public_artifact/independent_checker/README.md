# Second checker source tree (graph staged externally)

This is the separately implemented checker included in the coordinated release. It is intentionally source-only: `data/DSJC250.9.col` and its local `MANIFEST.sha256` are created only in a disposable scratch copy by `../scripts/stage_independent.py`. Run it through `../scripts/replay_independent.sh GRAPH`.

The checker uses Python's standard library, re-enumerates stable sets, checks the coloring and witnesses, verifies five rational payloads and six exact branch trees, and independently enumerates all 6,668 threshold profiles. It applies only conclusions returned by those verifiers to the exact matching profile conditions and top-set packings, and certifies only when no branch survives. See `PROOF_FORMAT.md` for the deliberately narrow release proof language.

It shares the proof-tree payloads, canonical column data, layered certificates, graph identity, and coloring with the integrated archive; see `../docs/SHARED_COMPONENTS.md`. It is implementation diversity, not unaffiliated research-group replication.
