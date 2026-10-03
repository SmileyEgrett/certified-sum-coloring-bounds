# Conditioned lower-bound reproduction: computational record

The run started on 30 September 2026 and finished on 1 October 2026. It generated and independently checked the four conditioned lower bounds. All 96 stages completed; two additional attempts were deferred before their mathematical process started because resource admission was not satisfied.

| Graph | Lower bound | Inclusive stage wall (s) | Timed child CPU (s) | Peak child RSS (KiB) |
|---|---:|---:|---:|---:|
| DSJC250.9 | 8,277 | 661.18 | 589.65 | 103,700 |
| DSJC500.9 | 29,791 | 1896.79 | 1638.28 | 289,204 |
| DSJC1000.9 | 102,344 | 8600.82 | 8425.15 | 529,916 |
| C2000.9 | 381,823 | 65.41 | 29.12 | 73,192 |

The enclosing execution process took 11265.96 s. Evidence export took a further 5.02 s: 11270.99 s (approximately 3 h 8 min) in total. Common checker compilation accounts for 6.58 s of the stage total.

Inclusive stage wall times contain input/source authentication, process startup, generation or verification, and output sealing. The enclosing total additionally contains orchestration and finalization outside those stages. The child CPU column is the sum of GNU time user and system times for the staged child processes. It excludes the supervising Python process; it is not total launch CPU time. Peak child RSS is the maximum of per-stage child peaks, not the aggregate memory peak.

The cgroup aggregate peak was 579,473,408 bytes, under a 4 GiB memory cap, with swap disabled and all mathematical work pinned to one CPU. No out-of-memory kill occurred. The generation stages had no imposed time or node limit. Software versions are recorded in `environment.json`; solver output includes the actual numerical backend version and thread settings.

**Accounting scope:** these are fresh reproduction costs, after the mathematical obligations, parameter choices and generator implementation had been prepared. They do not include historical discovery, failed exploratory approaches, software development or the separate complete integer-master comparison. They are not timings of the modern upper-witness search.

`stage-timings.json` contains all 98 attempt records. Each successful stage has `stdout.log`, `stderr.log`, GNU `process.time` and a `timing.json` record under `stages/`. Inner timers printed by programs are subintervals; do not add them to the inclusive totals. Machine-specific paths in transcripts have been replaced by descriptive placeholders. The exact proof objects and numerical arrays are retained byte-for-byte. The graph path in C2000.9 census metadata is relative.

The source map identifies the mathematical implementation used for these timings. The portable entry point preserves its stage arguments and mathematical routines, with recorded interpreter/path adaptations. Fresh use of that entry point creates a new source identity and new timing records.
