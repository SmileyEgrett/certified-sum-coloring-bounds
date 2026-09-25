# DSJC250.9 complete integer-master cross-check

The graph-derived all-stable-set/Ferrers model has 255 equations and 7125
variables: 6555 binary stable-set variables and 570 continuous unit-cell
variables. Two original one-thread HiGHS 1.11.0 runs reported conventional
floating-point MIP optimality at 8277, with 1601 nodes and 278786 LP iterations.
Both returned the same checked proper 73-class coloring, profile (2,4,29,37,1).
The exact lower proof remains the separate threshold/conditional certificates.

From the repository root:

```sh
./scripts/fetch_graphs.sh
./evidence/dsjc250/direct_integer_master/verify.sh graphs/DSJC250.9.col
```

The command must exit zero and end with
`DSJC250.9 DIRECT INTEGER MASTER STATIC VERIFICATION PASSED`.
Its C++20 checker verifies the complete stable-set universe, entire MPS matrix,
both original result vectors and returned colorings. It does not rerun HiGHS
or provide a new independently replayable MIP lower proof.

The ZIP contains the source, complete model, original result vectors and
solver logs. See [the archive guide](PUBLIC_REPACK.md) for its contents,
external graph requirement and pinned HiGHS source.

To materialize the runnable package without optimization:

```sh
./evidence/dsjc250/direct_integer_master/materialize.sh \
  graphs/DSJC250.9.col build/dsjc250-direct-master-package
```

Its optional `reproduce.sh NEW_OUTPUT CPU` downloads pinned public HiGHS source
with all upstream notices and repeats the original solves. The optional
optimization workflow is separate from static verification. Static
replay needs GCC/C++20, Bash, coreutils, unzip and standard Linux tools.
