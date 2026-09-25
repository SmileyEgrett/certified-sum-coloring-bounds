# Companion artifacts and verification scopes

The distribution contains the manuscript, its matching PDF, certificate and
witness data, checker sources, and reproduction instructions. Start with
[REPRODUCE.md](../REPRODUCE.md).

| Directory | Supplied evidence and scope |
| --- | --- |
| `paper/` | LaTeX, bibliography, thirteen table inputs and matching PDF. |
| `evidence/dsjc250/public_artifact/` | Exact threshold/conditional lower proof, checked coloring of sum 8277, two checker implementations and profile enumerators. |
| `evidence/dsjc250/direct_integer_master/` | Complete integer model, original HiGHS result vectors and logs, static model/coloring checker and optional solver reproduction recipe. |
| `evidence/dsjc500/dsjc500_integrated/` | Initial profile reduction, residual and conditional exclusions, 1,165-cell census, splitting paths and fixed-coloring certificate. |
| `evidence/dsjc500/fractional_profile_points/` | Three exact rational feasible points at 29791 and their bounded checker. |
| `evidence/dsjc1000/DSJC1000.9_EXACT_CONDITIONAL_RELEASE_20260728/` | Feasible unconditioned dual, eight conditional lower certificates and coloring of sum 103256. |
| `evidence/c2000_9/` | Top-layer packing certificate, coloring of sum 382379 using 402 classes, and exact fractional-coloring and sum-master primal/dual certificates. |

`PUBLIC_MANIFEST.sha256` lists every distribution file except itself. Run
`scripts/check_public_manifest.sh` on a clean extraction before fetching
graphs: it checks the exact file set as well as hashes. Package manifests
also bind the external graph files installed by `scripts/fetch_graphs.sh`.
Graph source URLs, byte identities and retrieval instructions are in
[GRAPH_PROVENANCE.md](GRAPH_PROVENANCE.md).

Hashes establish file identity. The mathematical checks additionally
reconstruct graph-derived column universes, bind certificate conclusions to
their stated models, check integer inequalities and verify colorings. The
DSJC250 implementations share proof data; their agreement provides
[implementation diversity](../evidence/dsjc250/public_artifact/docs/SHARED_COMPONENTS.md).
Descriptive solver metadata is not a proof premise.

The DSJC500 points establish continuous feasibility only. The DSJC1000
unconditioned dual is feasible and not optimal. The C2000 value 381823 is
the optimum of the stated floor-capped piecewise-linear relaxation, while
1948/5 is its ordinary fractional chromatic value. These LP statements do
not establish the integer chromatic sum.

The direct-master ZIP contains the numerical records needed to assess its
two HiGHS runs. See its [artifact guide](../evidence/dsjc250/direct_integer_master/PUBLIC_REPACK.md)
for contents, software sources and the distinction between static checking
and solver reproduction. [Component licenses](LICENSES.md) applies
to the distribution; public graph retrieval does not confer redistribution
rights.
