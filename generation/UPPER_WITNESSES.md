# Generating upper witnesses

The search and tail-optimization programs construct proper colorings. Their
objective is the sum obtained by labelling classes in nonincreasing order of
size. Every saved assignment is checked against the graph and its objective
is recomputed with integer arithmetic.

The [search program](sum-coloring-search/README.md) implements fixed-temperature
simulated annealing and a population search using overlaps between neighboring
replicas. Its optional restart operators create unused color classes by
splitting existing classes. The class-label comparison uses SciPy's bundled
C++ assignment solver. No Python SciPy installation is required for this C++
program.

The [tail optimizer](frozen-tail/README.md) fixes classes of size at least five,
enumerates all stable sets of the remaining graph and solves the resulting
integer partitioning model with HiGHS. For the supplied C2000.9 starting
assignment, the residual problem has 138 vertices and 2,051 stable sets. The
computed assignment has sum 382,379. Its model, solver log and independently
checked assignment are in `frozen-tail/example-output/`.

The programs can start new searches or continue from saved assignments. They
do not reconstruct the historical searches that produced every coloring in
the paper. Those upper bounds are established by the complete assignments in
`evidence/` and the companion's coloring checks. The C2000.9 example reproduces
the final tail-optimization step from its supplied starting assignment.

## Build and check

Run these commands from the companion root, with the benchmark inputs obtained
using `scripts/fetch_graphs.sh`. Build and test work is serial by default.

```sh
cmake -S generation/sum-coloring-search -B build/search -DCMAKE_BUILD_TYPE=Release
cmake --build build/search --parallel 1
ctest --test-dir build/search --output-on-failure --parallel 1
python3 -m venv build/tail-env
build/tail-env/bin/pip install -r generation/frozen-tail/requirements.txt
build/tail-env/bin/python generation/tests/benchmark_checks.py build/search/sum_coloring build/benchmark-checks .
build/tail-env/bin/python generation/tests/tail_checks.py generation/frozen-tail build/tail-checks graphs/C2000.9.col
```

The last two commands require new output directories. The benchmark checks
run one sweep from each released coloring in plain and population modes,
twice with the same seed. They check every edge, recompute the sum, and compare
assignments and search counts across repetitions. They test input compatibility
and repeatability; they do not measure how long a search needs to find the
paper's upper bounds from scratch.

The tail checks enumerate all partitions of every labelled four-vertex graph
as an independent oracle, exercise frozen-prefix and malformed-input cases,
then reproduce the C2000.9 finishing step. The recorded validation results
and their computational scope are in [validation/README.md](validation/README.md).

The C++ tests also run under address and undefined-behavior sanitizers when
configured with `-DSUM_COLORING_SANITIZERS=ON`. The optional OpenMP build was
checked with one worker. Multiworker trajectory reproducibility is not asserted.

Source code uses the MIT license; SciPy's bundled source retains its BSD
license. Documentation and generated example data use the companion's CC BY
4.0 license. The graph inputs retain their existing provenance and terms.
