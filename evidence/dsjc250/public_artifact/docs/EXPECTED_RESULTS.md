# Expected results

- `verify_release_manifest.py`: exit 0, `MANIFEST VERIFIED`.
- `check_graph.py`: exit 0; raw hash `1b90...83e7`, canonical hash `52be...3a8`, 250 vertices, 27,897 edges.
- integrated replay: exit 0; JSON `status` is `OPTIMALITY_CERTIFIED`, `threshold_profile_count=6668`, `layered_profile_count=45`, `parent_profile_count=16`, `unresolved_threshold_profiles=0`, incumbent canonical sum 8,277.
- second-checker replay: exit 0; JSON `verdict` is `OPTIMUM 8277 CERTIFIED`; stable-set counts are 3,228/2,869/205/3/0 and all 16 profiles are refuted.
- both profile enumerators: exit 0; counts 6,668/45/16 and byte-identical CSV output.
- mutation suite: exit 0 only after four altered scratch copies have each been rejected; final line `ALL MUTATION TESTS PASSED`.

Verifier/parser failure is nonzero. The integrated checker reserves exit 2 for verification/runtime failure and exit 3 for a completed non-certifying result. Wrapper usage errors use exit 64. The second checker and mutation suite use exit 1 for rejection/failure.
