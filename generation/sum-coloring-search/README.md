# Sum-coloring search

C++ software for finding proper colorings with small sums of color labels.
It provides fixed-temperature simulated annealing and a coupled population
search, with optional restarts. It reads a DIMACS graph and writes a complete
vertex-to-color assignment. The search supplies upper witnesses; it does not
certify a lower bound or optimality.

## Build

Requirements: a C++17 compiler and CMake 3.16 or later. Python 3 is used only
by the command-line tests. The assignment solver's C++ source is included;
installing Python SciPy is not necessary.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel 1
```

The default build uses one worker. For parallel replica sweeps, configure a
separate build with `-DSUM_COLORING_OPENMP=ON`, then explicitly set `--threads`.
Tests run only when requested:

```sh
ctest --test-dir build --output-on-failure --parallel 1
```

`-DSUM_COLORING_SANITIZERS=ON` enables address and undefined-behavior checks
with GCC or Clang. `-DBUILD_TESTING=OFF` builds only the search program.

## Run

```sh
./build/sum_coloring --graph examples/path.col --plain-sa 1 \
  --replicas 1 --threads 1 --sweeps 5 --seed 123 --temperature 1 \
  --save-best path-result.coloring
```

Every run requires a positive finite sweep count and a new output filename.
An existing output is rejected. The program saves the starting best coloring
and replaces its own checkpoint whenever a better coloring is found. SIGINT
or SIGTERM requests a stop after the current sweep. A sweep is a work unit,
not a wall-time limit.

Supply `--initial-coloring FILE` to start from a proper coloring. Otherwise,
each replica starts from an independently shuffled greedy coloring. Input
coloring files contain one `vertex color` pair per line, with positive
one-based indices; lines starting with `c` are comments. Arbitrary positive
color labels are normalized. Graph input must have a single `p edge n m`
or `p col n m` line and exactly `m` distinct non-loop edges. For a file whose
header counts edge incidences, use `--edge-count incidences`; it then requires
exactly `m/2` distinct edges. The companion's DSJC500.9 file uses this convention
(224,874 incidences, 112,437 edges); its other three benchmark files use the
default edge count. The convention is explicit, and duplicates and loops are
rejected in both modes. Supported graph
sizes are 1 to 10,000 vertices; available memory also limits practical size.

For a population search, use `--plain-sa 0` and set `--replicas`,
`--temperature`, and `--gamma`. Both temperature and gamma stay fixed during
a run. `--legal-repair auto` selects a scalar or bitset representation of the
same legal move set; either can also be selected explicitly. `--verify 1`
enables expensive consistency checks and is intended for small validation runs.

Optional restarts split randomly chosen vertices into separate unused color
slots. Enable them with `--kick-operator runway` and a positive
`--runway-slots`. At least one trigger must also be enabled:

- `--kick-collapse 1`: a replica is close to a frozen neighboring coloring;
  `--kick-distance` sets the distance threshold (default: integer `n/40`).
- `--kick-stagnation N`: no new replica best for `N` sweeps since its latest
  improvement or stagnation restart.
- `--kick-empty 1`: the sweep exhausts its legal candidate set.

Repeated triggers increase the requested split size, capped by
`--kick-max-size`. Unused color slots are exposed through these splits;
reserving capacity alone does not make them ordinary move destinations.
`--help` lists all options.

Save the command, graph, starting coloring, executable build information, and
standard output alongside each result. Seed reproducibility requires the same
implementation and parameters; this release does not promise identical
trajectories to historical builds or recovery of a particular published value.

## Algorithm

Each state is a proper partition into stable sets. Its objective is the sum
after assigning the smallest labels to the largest classes. If `q[s]` counts
classes of size at least `s`, the objective is
`sum_s q[s]*(q[s]+1)/2`. Moving a vertex from a class of size `a` to one of
size `b` changes that objective by
`q[b+1] + 1 - q[a] - (a == b+1)`.

A proposal moves one vertex to a different active class containing none of
its neighbors. Proposals are drawn uniformly from the current legal move set.
A sweep attempts `size_factor * n * active_slots` proposals per replica,
unless no legal move remains. Empty classes are removed between sweeps.

In plain SA, improvements and neutral moves are accepted; an increase `d`
is accepted with probability `exp(-d/T)`. In population mode each replica
also uses the frozen preceding and following replicas on a ring. For a pair
of vertices, assign spin -1 when they share a class and +1 otherwise. The
overlap score is the sum of products of these spins. Let `dK` be its change
against the two frozen neighbors. Improvements in the coloring sum are
accepted directly. Other moves use the acceptance factor
`exp(-d/T + beta*dK)`, where
`beta = -log(tanh(gamma/T))/2`.

Class intersection counts give `dK` without scanning all vertex pairs.
An upper bound on a favorable overlap change sometimes allows rejection
before evaluating those counts. All replicas finish their search sweeps
before the frozen states are updated. The completed states are frozen before
any restart splits, so a restarted state is not immediately substituted for
its frozen partner state.

The collapse trigger compares partitions independently of label names.
It forms the class intersection matrix and finds its maximum-weight
assignment. The distance is `n` minus that assignment weight. The assignment
routine is the unchanged C++ implementation of SciPy's
[linear sum assignment solver](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html),
which uses a modified Jonker–Volgenant algorithm. Source version, URLs, and
hashes are recorded in `third_party/scipy/UPSTREAM.json`.

## Files

- `src/sum_coloring.cpp`: replica sweeps, acceptance, restarts and reporting.
- `src/core.hpp`: state representation, exact objective updates, legal moves,
  overlap counts and consistency checks.
- `src/io.hpp`: command-line options, input validation and checkpoints.
- `src/assignment.hpp`: adapter to the assignment library.
- `third_party/scipy/`: pinned assignment implementation and its licence.
- `tests/`: exhaustive small-state and assignment-oracle checks, plus bounded
  command-line tests.

The author's code is provided under the MIT licence in `LICENSE-MIT`.
The bundled SciPy files retain their BSD licence and notices; see
`third_party/scipy/LICENSE.txt`.
