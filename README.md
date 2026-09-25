# Certified sum-coloring bounds

Companion manuscript and evidence for *Conditioning on the Largest Color Classes:
Certified Bounds for Minimum-Sum Coloring of Very Dense Benchmark Graphs*.

Version **1.0.0**. Cite this companion as: Olawale Titiloye (2026),
*Conditioning on the Largest Color Classes: Certified Bounds for Minimum-Sum
Coloring of Very Dense Benchmark Graphs — Software and Proof Certificates*,
version 1.0.0, Zenodo. [doi:10.5281/zenodo.22952311](https://doi.org/10.5281/zenodo.22952311).
Machine-readable citation metadata is provided in [CITATION.cff](CITATION.cff).

| Graph | Certified chromatic sum |
| --- | --- |
| DSJC250.9 | 8277 |
| DSJC500.9 | 29791..29848 |
| DSJC1000.9 | 102344..103256 |
| C2000.9 | 381823..382379 |

The lower bounds follow from exact certificates; every upper bound has a
checked proper coloring. The separate DSJC250.9 complete-master HiGHS runs
provide conventional floating-point solver corroboration. Their archive
does not supply an independently replayable MIP lower-proof tree.

- [Paper and matching PDF](paper/) and [build instructions](docs/PAPER_BUILD.md).
- [Artifact inventory and verification scopes](docs/PUBLIC_EXPORT.md).
- [Replay commands and dependencies](REPRODUCE.md).
- [Graph origins and exact hashes](docs/GRAPH_PROVENANCE.md); obtain the
  graph files with `./scripts/fetch_graphs.sh`.
- [Licenses](docs/LICENSES.md): MIT for original code; CC BY 4.0 for the
  manuscript, original documentation and certificate/witness data.

The DSJC500.9 census has 1,165 unresolved cells through 29,847, including three
at 29,791. Their [rational continuous points](evidence/dsjc500/fractional_profile_points/README.md)
are feasible points of the stated conditioned models, not integer colorings
or certificates of LP optimality.
