# Direct-master archive contents

`DSJC250.9_DIRECT_MSC_EXACT_20260918T213200Z_PUBLIC.zip` contains the complete
stable-set/Ferrers integer model and numerical records for the two documented
HiGHS 1.11.0 runs.

| Archive path | Role |
| --- | --- |
| `MODEL.md`, `SUMMARY.txt` | Formulation, evidence scope and recorded run statistics. |
| `source_snapshot/` | Stable-set/model generator, separate static checker and solver driver. |
| `results/generated/` | Complete stable-set universe, census and MPS model. |
| `results/lp/` | Continuous-relaxation solver records. |
| `results/mip01/`, `results/mip02/` | Original solver results, event logs and checked colorings. |
| `logs/` | Original solver stdout, stderr and resource measurements. |
| `reproduce.sh` | Optional solver-source acquisition, compilation and rerun recipe. |
| `SHA256SUMS` | All archive members except the manifest, plus the external graph identity. |

The outer `SHA256SUMS` binds the ZIP and static-replay sources.
`materialize.sh` first authenticates the graph and archive, extracts into a
new directory, installs the graph as `input/DSJC250.9.col` and verifies the
inner manifest. Static verification requires no solver installation.

The optional optimization recipe retrieves
[HiGHS 1.11.0 source](https://codeload.github.com/ERGO-Code/HiGHS/tar.gz/refs/tags/v1.11.0)
with SHA-256 `2b44b074cf41439325ce4d0bbdac2d51379f56faf17ba15320a410d3c1f07275`.
The fetched source includes its full upstream and third-party notices.
The package distributes no HiGHS binary or vendor tree.

Both recorded integer solutions give checked proper colorings of sum 8277.
The exact formulation and feasible witnesses are independently checked; the
solver's optimality status is conventional floating-point MIP evidence.
The separate threshold/conditional certificates supply the exact lower proof.
