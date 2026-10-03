#include "../src/core.hpp"
#include <functional>
#include <iostream>

using namespace sumsearch;
void require(bool ok, const char* message) { if (!ok) throw std::runtime_error(message); }

int64_t sorted_sum(const std::vector<int>& colors) {
    std::vector<int> sizes(colors.size() + 1, 0);
    for (int c : colors) ++sizes[c];
    std::sort(sizes.begin(), sizes.end(), std::greater<int>());
    int64_t value = 0;
    for (size_t i = 0; i < sizes.size(); ++i) value += (i + 1) * sizes[i];
    return value;
}

int brute_assignment(const std::vector<std::vector<int>>& w) {
    std::vector<int> permutation(w.size());
    std::iota(permutation.begin(), permutation.end(), 0);
    int best = 0;
    do {
        int sum = 0;
        for (size_t i = 0; i < w.size(); ++i) sum += w[i][permutation[i]];
        best = std::max(best, sum);
    } while (std::next_permutation(permutation.begin(), permutation.end()));
    return best;
}

int main() {
    try {
        uint64_t assignment_cases = 0, coloring_cases = 0, move_cases = 0;
        for (int mask = 0; mask < 512; ++mask) {
            std::vector<std::vector<int>> w(3, std::vector<int>(3));
            for (int i = 0; i < 9; ++i) w[i / 3][i % 3] = (mask >> i) & 1;
            require(maximum_assignment_weight(w) == brute_assignment(w), "binary assignment mismatch");
            ++assignment_cases;
        }
        Xoshiro256StarStar random(12345);
        for (int n = 1; n <= 6; ++n) for (int sample = 0; sample < 30; ++sample) {
            std::vector<std::vector<int>> w(n, std::vector<int>(n));
            for (auto& row : w) for (int& value : row) value = random.bounded_int(8);
            require(maximum_assignment_weight(w) == brute_assignment(w), "weighted assignment mismatch");
            ++assignment_cases;
        }
        require(maximum_assignment_weight({}) == 0, "empty assignment mismatch");
        require(partition_distance({0,0,1,1}, {2,2,0,0}, 3) == 0, "label invariance mismatch");
        require(partition_distance({0,0,1,1}, {0,1,0,1}, 2) == 2, "partition distance mismatch");
        std::vector<std::vector<int>> partitions;
        std::vector<int> labels(5, 0);
        std::function<void(int,int)> enumerate = [&](int pos, int largest) {
            if (pos == 5) { partitions.push_back(labels); return; }
            for (int c = 0; c <= largest + 1; ++c) {
                labels[pos] = c; enumerate(pos + 1, std::max(largest, c));
            }
        };
        enumerate(1, 0);
        for (int mask = 0; mask < 1024; ++mask) {
            Graph graph; graph.n = 5; graph.adj.resize(5);
            int bit = 0;
            for (int u = 0; u < 5; ++u) for (int v = u + 1; v < 5; ++v, ++bit)
                if ((mask >> bit) & 1) { graph.adj[u].push_back(v); graph.adj[v].push_back(u); ++graph.m; }
            BitGraph bits; bits.build(graph);
            for (const auto& coloring : partitions) {
                bool proper = true;
                for (int u = 0; u < 5; ++u) for (int v : graph.adj[u])
                    if (coloring[u] == coloring[v]) proper = false;
                if (!proper) continue;
                ++coloring_cases;
                ReplicaState state; state.build(graph, coloring, 5);
                // Exercise moves to an empty class as well as occupied classes.
                state.slots = std::min(5, state.slots + 1);
                require(state.sum.phi() == sorted_sum(coloring), "initial sum mismatch");
                LegalMoveSet scalar; scalar.build(state); scalar.verify(state);
                StableBitsetLegalMoveSet dense; dense.build(state, bits); dense.verify(state, bits);
                require(scalar.size() == dense.size(), "candidate counts differ");
                for (int i = 0; i < scalar.size(); ++i) require(scalar.move_at(i) == dense.move_at(i), "candidate order differs");
                auto frozen = coloring; std::reverse(frozen.begin(), frozen.end());
                FrozenOverlap overlap; overlap.build(state, frozen, color_span(frozen));
                int expected_count = 0;
                for (int v = 0; v < 5; ++v) for (int to = 0; to < state.slots; ++to) {
                    if (to == coloring[v]) continue;
                    bool legal = true;
                    for (int u : graph.adj[v]) if (coloring[u] == to) legal = false;
                    if (legal) ++expected_count;
                }
                require(expected_count == scalar.size(), "candidate universe incomplete");
                for (int i = 0; i < scalar.size(); ++i) {
                    const auto [v, to] = scalar.move_at(i);
                    const int from = coloring[v];
                    auto moved = coloring; moved[v] = to;
                    const int64_t delta = state.sum.delta(from, to);
                    require(delta == sorted_sum(moved) - sorted_sum(coloring), "objective delta mismatch");
                    require(overlap.delta(state, v, from, to) == exact_neighbor_kinetic(moved, frozen) -
                            exact_neighbor_kinetic(coloring, frozen), "overlap delta mismatch");
                    auto a = state, b = state; auto s = scalar; auto d = dense;
                    s.apply_accepted_move(graph, &a, v, from, to, delta);
                    d.apply_accepted_move(bits, &b, v, from, to, delta);
                    b.rebuild_adj_color(graph);
                    verify_state(graph, a); verify_state(graph, b);
                    require(a.color == b.color && a.sum.phi() == b.sum.phi(), "backend states differ");
                    require(s.size() == d.size(), "updated candidate counts differ");
                    for (int j = 0; j < s.size(); ++j) require(s.move_at(j) == d.move_at(j), "updated order differs");
                    a.compact_colors(); verify_state(graph, a);
                    require(a.sum.phi() == sorted_sum(moved), "compaction changes sum");
                    ++move_cases;
                }
                int64_t delta = 0;
                const int64_t before = state.sum.phi();
                apply_runway_split(graph, &state, 2, &random, &delta);
                verify_state(graph, state);
                require(state.sum.phi() == before + delta, "restart delta mismatch");
            }
        }
        std::cout << "assignment_cases=" << assignment_cases << " coloring_cases=" << coloring_cases
                  << " move_cases=" << move_cases << '\n';
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
