# Companion version 1.1.0

This release adds the software and computational records for generating the
paper's conditioned lower bounds, together with modern upper-witness search.
It retains the v1.0.0 manuscript and original evidence byte-for-byte.

- **Lower-bound generation:** enumeration, LP-based certificate construction,
  custom packing branching, exact rational reconstruction, and the C2000.9
  packing/clique-cover construction for all four graphs.
- **Fresh reproduction:** proof objects, numerical arrays, generation logs,
  software versions and per-stage costs. All four lower bounds were obtained
  and checked in a one-core reproduction under an aggregate 4 GiB memory cap.
- **Upper-witness software:** feasible simulated annealing and population
  search, using the supplied SciPy assignment implementation, plus frozen-tail
  integer optimization and benchmark/oracle tests.

The lower bounds remain 8,277, 29,791, 102,344 and 381,823. The original
checked upper witnesses remain unchanged. Reproduction timings describe
the recorded fresh computations, not the historical cost of discovering
the results. See [the computational record](../generation/conditioned-lower-bounds/reference/COMPUTATIONAL_RECORD.md)
and [generation workflow](../generation/conditioned-lower-bounds/GENERATION_WORKFLOW.md).

The paper's original version-specific Zenodo citation continues to identify
the evidence that accompanied it. The [concept DOI](https://doi.org/10.5281/zenodo.22952310)
provides access to the companion's versions. Code and data licenses remain as
described in [LICENSES.md](LICENSES.md), with third-party notices preserved in
the relevant software directory.
