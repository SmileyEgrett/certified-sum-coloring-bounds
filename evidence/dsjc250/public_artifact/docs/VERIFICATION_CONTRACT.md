# Verification contract

A successful proof replay consists of all of the following exact checks; generation success, optimizer status, floating-point output, and a precomputed verdict are not substitutes.

1. Bind the external graph to the recorded raw and canonical SHA-256 values, parse it strictly, and reproduce `n=250`, `m=27,897`.
2. Re-enumerate stable sets in deterministic increasing-tuple order through size six, obtaining counts `3228, 2869, 205, 3, 0` for sizes two through six.
3. Check the 8,277 coloring directly and reproduce its exact profile and sum.
4. Enumerate all 6,668 integer profiles satisfying the inclusive threshold `Phi<=8276`, where `Phi=sum_t g_t(g_t+1)/2`.
5. Check S1--S11 against their exact branch conditions. For every residual model, reconstruct the **complete** eligible column universe: all graph stable sets of every scored size, disjoint from the fixed top, in canonical order, subject only to the stated model restrictions. The selected maximum-class count is exactly the fixed top count; no additional size-five class may be selected. This does not assert that no other residual five-vertex stable subset exists in the graph.
6. Bind descriptor, model, canonical columns, proof payload, graph, and witness hashes. Supplied TSV rows are accepted only after exact equality with the reconstructed sequence.
7. For rational certificates, check every relevant column inequality and all objective/floor arithmetic with integers. Carry each verified bound and condition into profile filtering. For residual certificates, bind the exact fixed top sets and require `slack_budget = rhs_numerator - required_residual_sets*denominator` before using the bound.
8. For a tree, require a valid active root, strict postorder, every record reachable exactly once, no cycles or shared/orphan records, two children for every branch, an active branch variable, exact zero/one partition, conflict deletion, quota propagation, and a checked closure at every leaf.
9. At integer-dual leaves, quota multipliers are nonnegative and absent caps have multiplier zero. Close only under the strict inequality `selected_score*D + numerator < target*D`. Targets themselves encode forbidden `>=target` scores.
10. Refinement infeasibility is propagated only from a proved infeasible refinement back to its source profile.
11. Conclude optimality only after every threshold profile and every compatible maximum-class packing is eliminated by an actually applicable checked conclusion, all five rational and all six independent LPBB conclusions have a rejecting use, and the 8,277 witness is accepted.

The integrated proof language contains a matching/Tutte--Berge terminal type.
The independent checker rejects that terminal because its schema does not
carry the integrated checker's complete witness contract.  All six DSJC250.9
payloads in this release have zero matching leaves and close exclusively with
integer-dual leaves.
