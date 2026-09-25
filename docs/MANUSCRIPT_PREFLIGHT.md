# Active-source manuscript preflight

From the repository root, set `CHECK_WORK` to a new directory outside the
checkout and run:

```sh
bash scripts/check_manuscript.sh paper/paper.tex "$CHECK_WORK"
```

Dependencies are Bash, a C++20 compiler, GNU core utilities and Perl for the
retained bibliography cross-check. `CXX` may name a compiler executable.
The wrapper compiles the C++ helper into the new work directory, then checks
and exports the active source graph to `CHECK_WORK/active-source`. It runs
`scripts/check_bibliography.sh` only on that export. Compiler, preflight and
bibliography logs and exit statuses are retained. Success requires exit zero
and the final `MANUSCRIPT_CHECK_PASS` marker. Existing work directories are
rejected, so a previous binary or export cannot satisfy a new invocation.
The wrapper inherits CPU affinity and uses one thread.

The integrated manuscript has 14 active TeX files (the main file and thirteen
tables), one bibliography, 24 bibliography/cited keys and 80 labels. A clean
build must reconcile its project-local recorder inputs with this closure;
installed TeX packages and generated auxiliaries are separate. See
[PAPER_BUILD.md](PAPER_BUILD.md). The preflight output records the exact source closure for comparison with
the TeX recorder inputs.

## Supported checks and limits

The C++ helper follows literal local `input` and `include` dependencies from
the main manuscript directory and collects declared bibliography/graphic
files. It checks missing, unused and duplicate citation keys; duplicate labels
and undefined references; recognized dynamic constructs; and common raw-source
path/drafting markers. Comments use backslash parity, and recognized verbatim
and listing bodies are masked for dependency/citation/reference scanning.
Raw-source path/note checks still inspect comments and those literal bodies.
Repeated inputs are scanned repeatedly. Missing files, cycles and dependencies
that escape the manuscript root fail. Failed preflight creates no export;
an existing export is never overwritten.

This is literal-source lint, not general TeX interpretation. It does not expand
arbitrary macros, load package code, evaluate conditionals, verify bibliography
facts, determine alphabetical output, check mathematics or inspect a PDF.
Recognized unsupported syntax fails, but unknown package-defined commands and
some macro-hidden references are outside its supported subset. New dependency
or macro syntax requires manual review and recorder reconciliation. The
current notation macros and theorem declarations were inspected separately.

The retained shell bibliography checker is a second, directory-based regex
check. Running it on the active export removes inactive-file contamination;
it does not remove its limitations for verbatim examples, starred commands or
comment parity. A disagreement requires inspection. Neither checker is a
release-wide private-provenance or Git-history scanner. Source marker matches
are review aids, not a complete confidentiality guarantee.

The C++ helper exits 0 on success, 1 for detected source defects, and 2 for
fatal invocation/I/O errors. The wrapper propagates child failures. A passing
log with a nonzero process status is not a pass.

Run the bounded regression controls on a previously compiled helper, using
another new external directory:

```sh
bash scripts/tests/test_manuscript_preflight.sh \
  "$CHECK_WORK/manuscript_preflight" "$TEST_WORK"
```

The controls distinguish active/inactive files, comment/listing syntax,
missing/dynamic dependencies, reference and bibliography errors, export
preservation and wrapper failure propagation. They are not an exhaustive
TeX parser test suite.
