# Upper-witness software validation

The C++ search passed 692 assignment-oracle cases, 11,985 proper coloring
states and 119,290 legal-move checks. Release, address/undefined-behavior
sanitizer, and one-worker OpenMP builds passed the core and command-line suites.
All 32 bounded comparisons with the saved modern reference agreed, as did
32 serial/OpenMP comparisons with one worker. The reference comparisons cover
plain and population modes, scalar and bitset move sets, and restart triggers.

On the four paper graphs, 16 one-sweep runs from the supplied witnesses passed
independent properness and objective checks. All eight same-seed pairs produced
the same assignments and non-timing search counts. DSJC500.9's incidence-count
header is handled by its explicit `--edge-count incidences` option.

The tail optimizer matched brute-force optima on all 64 labelled four-vertex
graphs. Empty-tail, frozen-prefix, build-only and malformed-input tests also
passed. The C2000.9 finishing step reproduced a verified sum of 382,379 from
382,384. All coefficients and stable sets of its generated model match the
preserved finishing model. This validation took 7.404
seconds within the optimizer, including input checks, model construction,
solving and final verification; HiGHS reported 0.152
solver seconds. These are fresh reproduction measurements, not the cost of
discovering the starting coloring or the original upper witnesses.

Validation used one physical core of an Intel Core i9-7980XE and an aggregate
4 GiB cgroup memory cap with swap disabled. The largest measured scope peak
was 562.0 MiB; no out-of-memory event occurred. Python and
dependency versions, input hashes and per-run measurements are in `summary.json`.
The check commands are in `../UPPER_WITNESSES.md`.
