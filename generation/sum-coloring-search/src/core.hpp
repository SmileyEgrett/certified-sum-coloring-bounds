// Minimum-sum coloring search core.
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <functional>
#include <limits>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
#include "assignment.hpp"

namespace sumsearch {
[[noreturn]] inline void die(const std::string& message) {
    throw std::runtime_error(message);
}

struct Graph {
    int n = 0;
    int m = 0;
    std::vector<std::vector<int>> adj;
};

struct BitGraph {
    int n = 0;
    int words = 0;
    uint64_t last_mask = 0;
    std::vector<uint64_t> rows;

    void build(const Graph& graph) {
        n = graph.n;
        words = (n + 63) / 64;
        last_mask = n % 64 == 0
                        ? std::numeric_limits<uint64_t>::max()
                        : (uint64_t{1} << (n % 64)) - 1;
        rows.assign(static_cast<size_t>(n) * words, 0);
        for (int v = 0; v < n; ++v) {
            for (const int u : graph.adj[static_cast<size_t>(v)]) {
                rows[static_cast<size_t>(v) * words + u / 64] |=
                    uint64_t{1} << (u & 63);
            }
        }
    }

    const uint64_t* row(int v) const {
        return rows.data() + static_cast<size_t>(v) * words;
    }
};

bool auto_prefers_bitset_repair(const Graph& graph, int color_capacity) {
    constexpr size_t max_graph_bitset_bytes = size_t{256} << 20;
    const size_t words = (static_cast<size_t>(graph.n) + 63) / 64;
    if (words != 0 && static_cast<size_t>(graph.n) >
                          max_graph_bitset_bytes / sizeof(uint64_t) / words) {
        return false;
    }
    const size_t bytes =
        static_cast<size_t>(graph.n) * words * sizeof(uint64_t);
    if (bytes > max_graph_bitset_bytes) {
        return false;
    }

    const double mean_degree =
        2.0 * static_cast<double>(graph.m) / graph.n;
    const double mean_class_size =
        static_cast<double>(graph.n) / std::max(1, color_capacity);
    const double estimated_bit_words =
        (mean_class_size + 2.0) * static_cast<double>(words);
    return estimated_bit_words < mean_degree;
}

class alignas(64) Xoshiro256StarStar {
public:
    explicit Xoshiro256StarStar(uint64_t seed = 1) {
        for (uint64_t& word : state_) {
            word = splitmix64(&seed);
        }
    }

    uint64_t next_u64() {
        const uint64_t result = rotate_left(state_[1] * 5U, 7) * 9U;
        const uint64_t t = state_[1] << 17;
        state_[2] ^= state_[0];
        state_[3] ^= state_[1];
        state_[1] ^= state_[2];
        state_[0] ^= state_[3];
        state_[2] ^= t;
        state_[3] = rotate_left(state_[3], 45);
        return result;
    }

    int bounded_int(int bound) {
        if (bound <= 0) {
            die("RNG bound must be positive");
        }
        const uint64_t ubound = static_cast<uint64_t>(bound);
        const uint64_t threshold = (0U - ubound) % ubound;
        uint64_t value = 0;
        do {
            value = next_u64();
        } while (value < threshold);
        return static_cast<int>(value % ubound);
    }

    double uniform_open01() {
        constexpr double scale = 1.0 / 9007199254740992.0;
        return (static_cast<double>(next_u64() >> 11) + 0.5) * scale;
    }

    template <class T>
    void shuffle(std::vector<T>* values) {
        for (int i = static_cast<int>(values->size()) - 1; i > 0; --i) {
            const int j = bounded_int(i + 1);
            std::swap((*values)[static_cast<size_t>(i)],
                      (*values)[static_cast<size_t>(j)]);
        }
    }

private:
    uint64_t state_[4]{};

    static uint64_t rotate_left(uint64_t value, int shift) {
        return (value << shift) | (value >> (64 - shift));
    }

    static uint64_t splitmix64(uint64_t* state) {
        uint64_t z = (*state += 0x9E3779B97F4A7C15ULL);
        z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
        z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
        return z ^ (z >> 31);
    }
};

int64_t triangular(int64_t value) {
    return value * (value + 1) / 2;
}

class AcceptanceLookup {
public:
    AcceptanceLookup(
        int vertex_count,
        double temperature,
        double kinetic_coefficient)
        : max_phi_delta_(2 * vertex_count),
          max_kinetic_delta_(4 * std::max(0, vertex_count - 1)),
          inverse_temperature_(1.0 / temperature),
          kinetic_coefficient_(kinetic_coefficient),
          phi_factor_(static_cast<size_t>(2 * max_phi_delta_ + 1), 0.0),
          kinetic_factor_(
              static_cast<size_t>(2 * max_kinetic_delta_ + 1), 0.0) {
        for (int delta = -max_phi_delta_; delta <= max_phi_delta_; ++delta) {
            phi_factor_[static_cast<size_t>(delta + max_phi_delta_)] =
                bounded_exp(-static_cast<double>(delta) * inverse_temperature_);
        }
        for (int delta = -max_kinetic_delta_;
             delta <= max_kinetic_delta_;
             ++delta) {
            kinetic_factor_[static_cast<size_t>(
                delta + max_kinetic_delta_)] =
                bounded_exp(static_cast<double>(delta) * kinetic_coefficient_);
        }
    }

    bool accepts(int64_t delta_phi, int64_t delta_kinetic, double random) const {
        if (delta_phi < -max_phi_delta_ || delta_phi > max_phi_delta_ ||
            delta_kinetic < -max_kinetic_delta_ ||
            delta_kinetic > max_kinetic_delta_) {
            return fallback(delta_phi, delta_kinetic, random);
        }
        const double phi = phi_factor_[static_cast<size_t>(
            delta_phi + max_phi_delta_)];
        const double kinetic = kinetic_factor_[static_cast<size_t>(
            delta_kinetic + max_kinetic_delta_)];
        if (phi == 0.0 || kinetic == 0.0 || !std::isfinite(phi) ||
            !std::isfinite(kinetic)) {
            return fallback(delta_phi, delta_kinetic, random);
        }
        return kinetic > random / phi;
    }

private:
    int64_t max_phi_delta_ = 0;
    int64_t max_kinetic_delta_ = 0;
    double inverse_temperature_ = 0.0;
    double kinetic_coefficient_ = 0.0;
    std::vector<double> phi_factor_;
    std::vector<double> kinetic_factor_;

    static double bounded_exp(double exponent) {
        constexpr double max_exponent = 700.0;
        constexpr double min_exponent = -700.0;
        if (exponent >= max_exponent) {
            return std::numeric_limits<double>::infinity();
        }
        if (exponent <= min_exponent) {
            return 0.0;
        }
        return std::exp(exponent);
    }

    bool fallback(
        int64_t delta_phi,
        int64_t delta_kinetic,
        double random) const {
        const double exponent =
            -static_cast<double>(delta_phi) * inverse_temperature_ +
            static_cast<double>(delta_kinetic) * kinetic_coefficient_;
        return std::log(random) < exponent;
    }
};

int64_t favorable_kinetic_upper_bound(int source_size, int target_size) {
    return 4LL * (source_size + target_size - 1);
}

int64_t exact_phi_from_sizes(std::vector<int> sizes) {
    std::sort(sizes.begin(), sizes.end(), std::greater<int>());
    int64_t phi = 0;
    for (int i = 0; i < static_cast<int>(sizes.size()); ++i) {
        phi += static_cast<int64_t>(i + 1) * sizes[static_cast<size_t>(i)];
    }
    return phi;
}

class CanonicalSumTracker {
public:
    void initialize(const std::vector<int>& class_sizes, int vertex_count) {
        sizes_ = class_sizes;
        ge_.assign(static_cast<size_t>(vertex_count + 2), 0);
        std::vector<int> frequency(static_cast<size_t>(vertex_count + 1), 0);
        int total = 0;
        for (const int size : sizes_) {
            if (size < 0 || size > vertex_count) {
                die("invalid color-class size");
            }
            total += size;
            ++frequency[static_cast<size_t>(size)];
        }
        if (total != vertex_count) {
            die("color-class sizes do not sum to n");
        }
        for (int threshold = vertex_count; threshold >= 1; --threshold) {
            ge_[static_cast<size_t>(threshold)] =
                ge_[static_cast<size_t>(threshold + 1)] +
                frequency[static_cast<size_t>(threshold)];
        }
        phi_ = 0;
        for (const int count : ge_) {
            phi_ += triangular(count);
        }
    }

    int64_t delta(int from, int to) const {
        if (from == to || from < 0 || to < 0 ||
            from >= static_cast<int>(sizes_.size()) ||
            to >= static_cast<int>(sizes_.size())) {
            die("invalid canonical-sum move colors");
        }
        const int a = sizes_[static_cast<size_t>(from)];
        const int b = sizes_[static_cast<size_t>(to)];
        if (a <= 0) {
            die("canonical-sum move has empty source");
        }
        return static_cast<int64_t>(ge_[static_cast<size_t>(b + 1)]) + 1 -
               ge_[static_cast<size_t>(a)] - (a == b + 1 ? 1 : 0);
    }

    void apply(int from, int to, int64_t delta_value) {
        const int a = sizes_[static_cast<size_t>(from)];
        const int b = sizes_[static_cast<size_t>(to)];
        --ge_[static_cast<size_t>(a)];
        ++ge_[static_cast<size_t>(b + 1)];
        --sizes_[static_cast<size_t>(from)];
        ++sizes_[static_cast<size_t>(to)];
        phi_ += delta_value;
    }

    int size(int color) const {
        return sizes_[static_cast<size_t>(color)];
    }

    int ge(int threshold) const {
        return ge_[static_cast<size_t>(threshold)];
    }

    int64_t phi() const {
        return phi_;
    }

    const std::vector<int>& sizes() const {
        return sizes_;
    }

    void verify(int vertex_count) const {
        std::vector<int> exact_ge(static_cast<size_t>(vertex_count + 2), 0);
        for (const int size : sizes_) {
            for (int threshold = 1; threshold <= size; ++threshold) {
                ++exact_ge[static_cast<size_t>(threshold)];
            }
        }
        if (exact_ge != ge_) {
            die("canonical GE invariant mismatch");
        }
        int64_t conjugate_phi = 0;
        for (const int count : ge_) {
            conjugate_phi += triangular(count);
        }
        const int64_t sorted_phi = exact_phi_from_sizes(sizes_);
        if (phi_ != conjugate_phi || phi_ != sorted_phi) {
            die("canonical objective invariant mismatch");
        }
    }

private:
    std::vector<int> sizes_;
    std::vector<int> ge_;
    int64_t phi_ = 0;
};

std::vector<int> random_greedy_coloring(
    const Graph& graph,
    Xoshiro256StarStar* rng) {
    std::vector<int> order(static_cast<size_t>(graph.n));
    std::iota(order.begin(), order.end(), 0);
    rng->shuffle(&order);

    std::vector<int> color(static_cast<size_t>(graph.n), -1);
    std::vector<int> blocked(static_cast<size_t>(graph.n), -1);
    int color_count = 0;
    for (const int v : order) {
        for (const int u : graph.adj[static_cast<size_t>(v)]) {
            const int c = color[static_cast<size_t>(u)];
            if (c >= 0) {
                blocked[static_cast<size_t>(c)] = v;
            }
        }
        int selected = 0;
        while (selected < color_count &&
               blocked[static_cast<size_t>(selected)] == v) {
            ++selected;
        }
        if (selected == color_count) {
            ++color_count;
        }
        color[static_cast<size_t>(v)] = selected;
    }
    return color;
}

struct alignas(64) ReplicaState {
    int capacity = 0;
    int slots = 0;      // label span; compacted at sweep boundaries
    int occupied = 0;   // exact nonempty-class count between compactions
    std::vector<int> color;
    std::vector<std::vector<int>> adj_color;
    CanonicalSumTracker sum;

    void build(const Graph& graph, std::vector<int> initial_color, int color_capacity) {
        capacity = color_capacity;
        color = std::move(initial_color);
        slots = 0;
        std::vector<int> sizes(static_cast<size_t>(capacity), 0);
        for (const int c : color) {
            if (c < 0 || c >= capacity) {
                die("initial color outside capacity");
            }
            ++sizes[static_cast<size_t>(c)];
            slots = std::max(slots, c + 1);
        }
        sum.initialize(sizes, graph.n);
        occupied = static_cast<int>(std::count_if(
            sizes.begin(), sizes.end(), [](int size) { return size > 0; }));
        adj_color.assign(
            static_cast<size_t>(graph.n),
            std::vector<int>(static_cast<size_t>(capacity), 0));
        for (int v = 0; v < graph.n; ++v) {
            for (const int u : graph.adj[static_cast<size_t>(v)]) {
                ++adj_color[static_cast<size_t>(v)]
                           [static_cast<size_t>(color[static_cast<size_t>(u)])];
            }
        }
    }

    void apply_move(
        const Graph& graph,
        int v,
        int from,
        int to,
        int64_t delta_phi) {
        const bool empties_source = sum.size(from) == 1;
        const bool fills_target = sum.size(to) == 0;
        occupied += static_cast<int>(fills_target) -
                    static_cast<int>(empties_source);
        sum.apply(from, to, delta_phi);
        for (const int u : graph.adj[static_cast<size_t>(v)]) {
            --adj_color[static_cast<size_t>(u)][static_cast<size_t>(from)];
            ++adj_color[static_cast<size_t>(u)][static_cast<size_t>(to)];
        }
        color[static_cast<size_t>(v)] = to;
    }

    void rebuild_adj_color(const Graph& graph) {
        for (std::vector<int>& row : adj_color) {
            std::fill(row.begin(), row.end(), 0);
        }
        for (int v = 0; v < graph.n; ++v) {
            for (const int u : graph.adj[static_cast<size_t>(v)]) {
                ++adj_color[static_cast<size_t>(v)]
                           [static_cast<size_t>(color[static_cast<size_t>(u)])];
            }
        }
    }

    void compact_colors() {
        std::vector<int> mapping(static_cast<size_t>(slots), -1);
        int next = 0;
        for (int c = 0; c < slots; ++c) {
            if (sum.size(c) > 0) {
                mapping[static_cast<size_t>(c)] = next++;
            }
        }
        if (next == slots) {
            return;
        }
        for (int& c : color) {
            c = mapping[static_cast<size_t>(c)];
        }
        for (std::vector<int>& row : adj_color) {
            std::vector<int> compacted(static_cast<size_t>(capacity), 0);
            for (int old = 0; old < slots; ++old) {
                const int replacement = mapping[static_cast<size_t>(old)];
                if (replacement >= 0) {
                    compacted[static_cast<size_t>(replacement)] =
                        row[static_cast<size_t>(old)];
                }
            }
            row.swap(compacted);
        }
        std::vector<int> sizes(static_cast<size_t>(capacity), 0);
        for (int old = 0; old < slots; ++old) {
            const int replacement = mapping[static_cast<size_t>(old)];
            if (replacement >= 0) {
                sizes[static_cast<size_t>(replacement)] = sum.size(old);
            }
        }
        slots = next;
        if (next != occupied) {
            die("occupied-color count mismatch during compaction");
        }
        sum.initialize(sizes, static_cast<int>(color.size()));
    }
};

class LegalMoveSet {
public:
    void build(const ReplicaState& state) {
        vertex_count_ = static_cast<int>(state.color.size());
        color_capacity_ = state.capacity;
        moves_.clear();
        position_.assign(
            static_cast<size_t>(vertex_count_) * color_capacity_, -1);
        moves_.reserve(
            static_cast<size_t>(vertex_count_) * state.slots);
        for (int v = 0; v < vertex_count_; ++v) {
            for (int to = 0; to < state.slots; ++to) {
                if (to != state.color[static_cast<size_t>(v)] &&
                    state.adj_color[static_cast<size_t>(v)]
                                   [static_cast<size_t>(to)] == 0) {
                    add(v, to);
                }
            }
        }
    }

    bool empty() const {
        return moves_.empty();
    }

    int size() const {
        return static_cast<int>(moves_.size());
    }

    std::pair<int, int> move_at(int index) const {
        const int encoded = moves_[static_cast<size_t>(index)];
        return {encoded % vertex_count_, encoded / vertex_count_};
    }

    std::pair<int, int> sample(Xoshiro256StarStar* rng) const {
        if (moves_.empty()) {
            die("cannot sample an empty legal-move set");
        }
        const int encoded =
            moves_[static_cast<size_t>(rng->bounded_int(size()))];
        return {encoded % vertex_count_, encoded / vertex_count_};
    }

    void apply_accepted_move(
        const Graph& graph,
        ReplicaState* state,
        int v,
        int from,
        int to,
        int64_t delta_phi) {
        const bool empties_source = state->sum.size(from) == 1;
        const bool fills_target = state->sum.size(to) == 0;
        state->occupied += static_cast<int>(fills_target) -
                           static_cast<int>(empties_source);
        state->sum.apply(from, to, delta_phi);

        erase(v, to);
        if (state->adj_color[static_cast<size_t>(v)]
                            [static_cast<size_t>(from)] == 0) {
            add(v, from);
        }
        for (const int u : graph.adj[static_cast<size_t>(v)]) {
            int& from_count =
                state->adj_color[static_cast<size_t>(u)]
                                [static_cast<size_t>(from)];
            --from_count;
            if (state->color[static_cast<size_t>(u)] != from &&
                from_count == 0) {
                add(u, from);
            }

            int& to_count =
                state->adj_color[static_cast<size_t>(u)]
                                [static_cast<size_t>(to)];
            const bool target_zero_crossing = to_count == 0;
            ++to_count;
            if (target_zero_crossing) {
                erase(u, to);
            }
        }
        state->color[static_cast<size_t>(v)] = to;
    }

    void verify(const ReplicaState& state) const {
        if (vertex_count_ != static_cast<int>(state.color.size()) ||
            color_capacity_ != state.capacity) {
            die("legal-move dimensions mismatch");
        }
        std::vector<uint8_t> exact(position_.size(), 0);
        for (int v = 0; v < vertex_count_; ++v) {
            for (int to = 0; to < state.slots; ++to) {
                if (to != state.color[static_cast<size_t>(v)] &&
                    state.adj_color[static_cast<size_t>(v)]
                                   [static_cast<size_t>(to)] == 0) {
                    exact[static_cast<size_t>(encode(v, to))] = 1;
                }
            }
        }
        if (moves_.size() != static_cast<size_t>(
                std::count(exact.begin(), exact.end(), uint8_t{1}))) {
            die("legal-move set size mismatch");
        }
        for (int index = 0; index < static_cast<int>(moves_.size()); ++index) {
            const int encoded = moves_[static_cast<size_t>(index)];
            if (encoded < 0 ||
                encoded >= static_cast<int>(position_.size()) ||
                exact[static_cast<size_t>(encoded)] == 0 ||
                position_[static_cast<size_t>(encoded)] != index) {
                die("legal-move set membership mismatch");
            }
        }
        for (int encoded = 0;
             encoded < static_cast<int>(position_.size());
             ++encoded) {
            if ((position_[static_cast<size_t>(encoded)] >= 0) !=
                (exact[static_cast<size_t>(encoded)] != 0)) {
                die("legal-move position-map mismatch");
            }
        }
    }

private:
    int vertex_count_ = 0;
    int color_capacity_ = 0;
    std::vector<int> moves_;
    std::vector<int> position_;

    int encode(int v, int to) const {
        return to * vertex_count_ + v;
    }

    void add(int v, int to) {
        const int encoded = encode(v, to);
        int& position = position_[static_cast<size_t>(encoded)];
        if (position >= 0) {
            return;
        }
        position = static_cast<int>(moves_.size());
        moves_.push_back(encoded);
    }

    void erase(int v, int to) {
        const int encoded = encode(v, to);
        int& position = position_[static_cast<size_t>(encoded)];
        if (position < 0) {
            return;
        }
        const int last = moves_.back();
        moves_[static_cast<size_t>(position)] = last;
        position_[static_cast<size_t>(last)] = position;
        moves_.pop_back();
        position = -1;
    }
};

class StableBitsetLegalMoveSet {
public:
    void build(const ReplicaState& state, const BitGraph& graph) {
        vertex_count_ = static_cast<int>(state.color.size());
        color_capacity_ = state.capacity;
        slots_ = state.slots;
        words_ = graph.words;
        moves_.clear();
        position_.assign(
            static_cast<size_t>(vertex_count_) * color_capacity_, -1);
        moves_.reserve(static_cast<size_t>(vertex_count_) * slots_);
        blocked_.assign(static_cast<size_t>(color_capacity_) * words_, 0);
        members_.assign(static_cast<size_t>(color_capacity_), {});
        member_position_.assign(static_cast<size_t>(vertex_count_), -1);
        old_from_.assign(static_cast<size_t>(words_), 0);
        from_diff_.assign(static_cast<size_t>(words_), 0);
        to_diff_.assign(static_cast<size_t>(words_), 0);

        for (int v = 0; v < vertex_count_; ++v) {
            const int c = state.color[static_cast<size_t>(v)];
            member_position_[static_cast<size_t>(v)] =
                static_cast<int>(members_[static_cast<size_t>(c)].size());
            members_[static_cast<size_t>(c)].push_back(v);
        }
        for (int c = 0; c < slots_; ++c) {
            uint64_t* out = blocked_row(c);
            for (const int v : members_[static_cast<size_t>(c)]) {
                const uint64_t* in = graph.row(v);
                for (int w = 0; w < words_; ++w) {
                    out[w] |= in[w];
                }
            }
        }
        for (int v = 0; v < vertex_count_; ++v) {
            for (int to = 0; to < slots_; ++to) {
                if (to != state.color[static_cast<size_t>(v)] &&
                    !blocked(to, v)) {
                    add(v, to);
                }
            }
        }
    }

    bool empty() const {
        return moves_.empty();
    }

    int size() const {
        return static_cast<int>(moves_.size());
    }

    std::pair<int, int> move_at(int index) const {
        const int encoded = moves_[static_cast<size_t>(index)];
        return {encoded % vertex_count_, encoded / vertex_count_};
    }

    std::pair<int, int> sample(Xoshiro256StarStar* rng) const {
        if (moves_.empty()) {
            die("cannot sample an empty stable-bitset legal-move set");
        }
        const int encoded =
            moves_[static_cast<size_t>(rng->bounded_int(size()))];
        return {encoded % vertex_count_, encoded / vertex_count_};
    }

    void apply_accepted_move(
        const BitGraph& graph,
        ReplicaState* state,
        int v,
        int from,
        int to,
        int64_t delta_phi) {
        const bool empties_source = state->sum.size(from) == 1;
        const bool fills_target = state->sum.size(to) == 0;
        state->occupied += static_cast<int>(fills_target) -
                           static_cast<int>(empties_source);
        state->sum.apply(from, to, delta_phi);

        std::vector<int>& source = members_[static_cast<size_t>(from)];
        const int source_position = member_position_[static_cast<size_t>(v)];
        const int last = source.back();
        source[static_cast<size_t>(source_position)] = last;
        member_position_[static_cast<size_t>(last)] = source_position;
        source.pop_back();
        std::vector<int>& target = members_[static_cast<size_t>(to)];
        member_position_[static_cast<size_t>(v)] =
            static_cast<int>(target.size());
        target.push_back(v);

        uint64_t* source_blocked = blocked_row(from);
        uint64_t* target_blocked = blocked_row(to);
        std::copy(
            source_blocked, source_blocked + words_, old_from_.begin());
        std::fill(source_blocked, source_blocked + words_, uint64_t{0});
        for (const int member : source) {
            const uint64_t* row = graph.row(member);
            for (int w = 0; w < words_; ++w) {
                source_blocked[w] |= row[w];
            }
        }
        const uint64_t* moved_neighbors = graph.row(v);
        for (int w = 0; w < words_; ++w) {
            from_diff_[static_cast<size_t>(w)] =
                old_from_[static_cast<size_t>(w)] & ~source_blocked[w];
            to_diff_[static_cast<size_t>(w)] =
                moved_neighbors[w] & ~target_blocked[w];
            target_blocked[w] |= moved_neighbors[w];
        }

        erase(v, to);
        add(v, from);
        for (int w = 0; w < words_; ++w) {
            uint64_t pending = from_diff_[static_cast<size_t>(w)] |
                               to_diff_[static_cast<size_t>(w)];
            while (pending != 0) {
                const int bit = __builtin_ctzll(pending);
                const int u = 64 * w + bit;
                const uint64_t flag = uint64_t{1} << bit;
                if ((from_diff_[static_cast<size_t>(w)] & flag) != 0) {
                    add(u, from);
                }
                if ((to_diff_[static_cast<size_t>(w)] & flag) != 0) {
                    erase(u, to);
                }
                pending &= pending - 1;
            }
        }
        state->color[static_cast<size_t>(v)] = to;
    }

    void verify(const ReplicaState& state, const BitGraph& graph) const {
        std::vector<uint64_t> exact(blocked_.size(), 0);
        std::vector<uint8_t> seen(static_cast<size_t>(vertex_count_), 0);
        for (int c = 0; c < color_capacity_; ++c) {
            const std::vector<int>& members = members_[static_cast<size_t>(c)];
            for (int index = 0;
                 index < static_cast<int>(members.size()); ++index) {
                const int v = members[static_cast<size_t>(index)];
                if (v < 0 || v >= vertex_count_ ||
                    state.color[static_cast<size_t>(v)] != c ||
                    member_position_[static_cast<size_t>(v)] != index ||
                    seen[static_cast<size_t>(v)] != 0) {
                    die("stable-bitset class-membership invariant mismatch");
                }
                seen[static_cast<size_t>(v)] = 1;
            }
        }
        if (std::count(seen.begin(), seen.end(), uint8_t{1}) != vertex_count_) {
            die("stable-bitset class-membership coverage mismatch");
        }
        for (int v = 0; v < vertex_count_; ++v) {
            const int c = state.color[static_cast<size_t>(v)];
            const uint64_t* in = graph.row(v);
            uint64_t* out = exact.data() + static_cast<size_t>(c) * words_;
            for (int w = 0; w < words_; ++w) {
                out[w] |= in[w];
            }
        }
        if (exact != blocked_) {
            die("stable-bitset blocked-color invariant mismatch");
        }
        verify_dense_membership(state);
    }

private:
    int vertex_count_ = 0;
    int color_capacity_ = 0;
    int slots_ = 0;
    int words_ = 0;
    std::vector<int> moves_;
    std::vector<int> position_;
    std::vector<uint64_t> blocked_;
    std::vector<std::vector<int>> members_;
    std::vector<int> member_position_;
    std::vector<uint64_t> old_from_;
    std::vector<uint64_t> from_diff_;
    std::vector<uint64_t> to_diff_;

    int encode(int v, int to) const {
        return to * vertex_count_ + v;
    }

    uint64_t* blocked_row(int color) {
        return blocked_.data() + static_cast<size_t>(color) * words_;
    }

    bool blocked(int color, int v) const {
        return (blocked_[static_cast<size_t>(color) * words_ + v / 64] &
                (uint64_t{1} << (v & 63))) != 0;
    }

    void add(int v, int to) {
        const int encoded = encode(v, to);
        int& position = position_[static_cast<size_t>(encoded)];
        if (position >= 0) {
            return;
        }
        position = static_cast<int>(moves_.size());
        moves_.push_back(encoded);
    }

    void erase(int v, int to) {
        const int encoded = encode(v, to);
        int& position = position_[static_cast<size_t>(encoded)];
        if (position < 0) {
            return;
        }
        const int last = moves_.back();
        moves_[static_cast<size_t>(position)] = last;
        position_[static_cast<size_t>(last)] = position;
        moves_.pop_back();
        position = -1;
    }

    void verify_dense_membership(const ReplicaState& state) const {
        std::vector<uint8_t> membership(position_.size(), 0);
        for (int v = 0; v < vertex_count_; ++v) {
            for (int to = 0; to < slots_; ++to) {
                if (to != state.color[static_cast<size_t>(v)] &&
                    !blocked(to, v)) {
                    membership[static_cast<size_t>(encode(v, to))] = 1;
                }
            }
        }
        if (moves_.size() != static_cast<size_t>(std::count(
                membership.begin(), membership.end(), uint8_t{1}))) {
            die("stable-bitset candidate-set size mismatch");
        }
        for (int index = 0; index < static_cast<int>(moves_.size()); ++index) {
            const int encoded = moves_[static_cast<size_t>(index)];
            if (membership[static_cast<size_t>(encoded)] == 0 ||
                position_[static_cast<size_t>(encoded)] != index) {
                die("stable-bitset candidate-set membership mismatch");
            }
        }
        for (int encoded = 0;
             encoded < static_cast<int>(position_.size()); ++encoded) {
            if ((position_[static_cast<size_t>(encoded)] >= 0) !=
                (membership[static_cast<size_t>(encoded)] != 0)) {
                die("stable-bitset candidate position-map mismatch");
            }
        }
    }
};

struct FrozenOverlap {
    const std::vector<int>* saved_color = nullptr;
    int current_capacity = 0;
    int saved_slots = 0;
    std::vector<int> counts;

    void build(
        const ReplicaState& current,
        const std::vector<int>& frozen,
        int frozen_slots) {
        saved_color = &frozen;
        current_capacity = current.capacity;
        saved_slots = frozen_slots;
        counts.assign(
            static_cast<size_t>(current_capacity) *
                static_cast<size_t>(saved_slots),
            0);
        for (int v = 0; v < static_cast<int>(current.color.size()); ++v) {
            ++at(current.color[static_cast<size_t>(v)],
                 frozen[static_cast<size_t>(v)]);
        }
    }

    int& at(int current_class, int saved_class) {
        return counts[static_cast<size_t>(current_class) * saved_slots +
                      static_cast<size_t>(saved_class)];
    }

    int at(int current_class, int saved_class) const {
        return counts[static_cast<size_t>(current_class) * saved_slots +
                      static_cast<size_t>(saved_class)];
    }

    int64_t delta(
        const ReplicaState& current,
        int v,
        int from,
        int to) const {
        const int a = current.sum.size(from);
        const int b = current.sum.size(to);
        const int saved = (*saved_color)[static_cast<size_t>(v)];
        const int old_matches = at(from, saved);
        const int new_matches = at(to, saved);
        return 2LL *
               (a + 1 - b - 2 * old_matches + 2 * new_matches);
    }

    void apply(int v, int from, int to) {
        const int saved = (*saved_color)[static_cast<size_t>(v)];
        --at(from, saved);
        ++at(to, saved);
    }

    void verify(const ReplicaState& current) const {
        std::vector<int> exact(counts.size(), 0);
        for (int v = 0; v < static_cast<int>(current.color.size()); ++v) {
            const int c = current.color[static_cast<size_t>(v)];
            const int s = (*saved_color)[static_cast<size_t>(v)];
            ++exact[static_cast<size_t>(c) * saved_slots + s];
        }
        if (exact != counts) {
            die("frozen overlap invariant mismatch");
        }
    }
};

int exact_conflicts(const Graph& graph, const std::vector<int>& color) {
    int conflicts = 0;
    for (int v = 0; v < graph.n; ++v) {
        for (const int u : graph.adj[static_cast<size_t>(v)]) {
            if (u > v && color[static_cast<size_t>(u)] ==
                             color[static_cast<size_t>(v)]) {
                ++conflicts;
            }
        }
    }
    return conflicts;
}

std::vector<int> read_initial_coloring(
    const std::string& path,
    const Graph& graph) {
    std::ifstream in(path);
    if (!in) {
        die("failed to open initial coloring: " + path);
    }

    std::vector<int> color(static_cast<size_t>(graph.n), -1);
    std::string line;
    int line_number = 0;
    while (std::getline(in, line)) {
        ++line_number;
        std::istringstream row(line);
        row >> std::ws;
        if (row.eof() || row.peek() == 'c' || row.peek() == 'C') {
            continue;
        }
        int vertex = 0;
        int label = 0;
        std::string extra;
        if (!(row >> vertex >> label) || (row >> extra)) {
            die("invalid initial-coloring line " +
                std::to_string(line_number));
        }
        if (vertex < 1 || vertex > graph.n || label < 1) {
            die("initial-coloring value out of range on line " +
                std::to_string(line_number));
        }
        int& assigned = color[static_cast<size_t>(vertex - 1)];
        if (assigned != -1) {
            die("duplicate initial-coloring vertex " +
                std::to_string(vertex));
        }
        assigned = label;
    }

    for (int v = 0; v < graph.n; ++v) {
        if (color[static_cast<size_t>(v)] < 0) {
            die("missing initial-coloring vertex " + std::to_string(v + 1));
        }
    }

    std::vector<int> labels = color;
    std::sort(labels.begin(), labels.end());
    labels.erase(std::unique(labels.begin(), labels.end()), labels.end());
    for (int& label : color) {
        label = static_cast<int>(
            std::lower_bound(labels.begin(), labels.end(), label) -
            labels.begin());
    }
    if (exact_conflicts(graph, color) != 0) {
        die("initial coloring is not proper");
    }
    return color;
}

void verify_state(
    const Graph& graph,
    const ReplicaState& state,
    const std::vector<FrozenOverlap>* overlaps = nullptr) {
    if (state.slots <= 0 || state.slots > state.capacity) {
        die("invalid active color-slot count");
    }
    std::vector<int> sizes(static_cast<size_t>(state.capacity), 0);
    for (const int c : state.color) {
        if (c < 0 || c >= state.slots) {
            die("vertex color outside active slots");
        }
        ++sizes[static_cast<size_t>(c)];
    }
    if (sizes != state.sum.sizes()) {
        die("class-size invariant mismatch");
    }
    const int exact_occupied = static_cast<int>(std::count_if(
        sizes.begin(), sizes.end(), [](int size) { return size > 0; }));
    if (state.occupied != exact_occupied) {
        die("occupied-color count invariant mismatch");
    }
    if (exact_conflicts(graph, state.color) != 0) {
        die("sum-coloring state is not proper");
    }
    std::vector<std::vector<int>> exact(
        static_cast<size_t>(graph.n),
        std::vector<int>(static_cast<size_t>(state.capacity), 0));
    for (int v = 0; v < graph.n; ++v) {
        for (const int u : graph.adj[static_cast<size_t>(v)]) {
            ++exact[static_cast<size_t>(v)]
                   [static_cast<size_t>(state.color[static_cast<size_t>(u)])];
        }
    }
    if (exact != state.adj_color) {
        die("adjacent-color frequency invariant mismatch");
    }
    state.sum.verify(graph.n);
    if (overlaps != nullptr) {
        for (const FrozenOverlap& overlap : *overlaps) {
            overlap.verify(state);
        }
    }
}

void verify_state_without_adj(
    const Graph& graph,
    const ReplicaState& state,
    const std::vector<FrozenOverlap>* overlaps = nullptr) {
    if (state.slots <= 0 || state.slots > state.capacity) {
        die("invalid active color-slot count");
    }
    std::vector<int> sizes(static_cast<size_t>(state.capacity), 0);
    for (const int c : state.color) {
        if (c < 0 || c >= state.slots) {
            die("vertex color outside active slots");
        }
        ++sizes[static_cast<size_t>(c)];
    }
    if (sizes != state.sum.sizes()) {
        die("class-size invariant mismatch");
    }
    const int exact_occupied = static_cast<int>(std::count_if(
        sizes.begin(), sizes.end(), [](int size) { return size > 0; }));
    if (state.occupied != exact_occupied) {
        die("occupied-color count invariant mismatch");
    }
    if (exact_conflicts(graph, state.color) != 0) {
        die("sum-coloring state is not proper");
    }
    state.sum.verify(graph.n);
    if (overlaps != nullptr) {
        for (const FrozenOverlap& overlap : *overlaps) {
            overlap.verify(state);
        }
    }
}

int partition_distance(
    const std::vector<int>& first,
    const std::vector<int>& second,
    int color_capacity) {
    if (first.size() != second.size() || color_capacity <= 0) {
        die("invalid partition-distance dimensions");
    }
    std::vector<std::vector<int>> overlap(
        static_cast<size_t>(color_capacity),
        std::vector<int>(static_cast<size_t>(color_capacity), 0));
    for (int v = 0; v < static_cast<int>(first.size()); ++v) {
        const int a = first[static_cast<size_t>(v)];
        const int b = second[static_cast<size_t>(v)];
        if (a < 0 || a >= color_capacity ||
            b < 0 || b >= color_capacity) {
            die("partition-distance color outside capacity");
        }
        ++overlap[static_cast<size_t>(a)][static_cast<size_t>(b)];
    }
    return static_cast<int>(first.size()) - maximum_assignment_weight(overlap);
}

int apply_runway_split(
    const Graph& graph,
    ReplicaState* state,
    int requested_vertices,
    Xoshiro256StarStar* rng,
    int64_t* delta_phi) {
    if (requested_vertices <= 0) {
        die("invalid runway-kick size");
    }
    state->compact_colors();
    const int available = state->capacity - state->slots;
    const int moved = std::min({requested_vertices, available, graph.n});
    if (moved <= 0) {
        *delta_phi = 0;
        return 0;
    }

    std::vector<int> vertices(static_cast<size_t>(graph.n));
    std::iota(vertices.begin(), vertices.end(), 0);
    rng->shuffle(&vertices);
    const int first_empty = state->slots;
    const int64_t before = state->sum.phi();
    for (int i = 0; i < moved; ++i) {
        const int v = vertices[static_cast<size_t>(i)];
        const int from = state->color[static_cast<size_t>(v)];
        const int to = first_empty + i;
        const int64_t delta = state->sum.delta(from, to);
        state->apply_move(graph, v, from, to, delta);
    }
    state->slots = first_empty + moved;
    state->compact_colors();
    *delta_phi = state->sum.phi() - before;
    return moved;
}

int64_t exact_neighbor_kinetic(
    const std::vector<int>& current,
    const std::vector<int>& saved) {
    int64_t energy = 0;
    for (int i = 0; i < static_cast<int>(current.size()); ++i) {
        for (int j = 0; j < i; ++j) {
            const int current_spin =
                current[static_cast<size_t>(i)] ==
                        current[static_cast<size_t>(j)]
                    ? -1
                    : 1;
            const int saved_spin =
                saved[static_cast<size_t>(i)] == saved[static_cast<size_t>(j)]
                    ? -1
                    : 1;
            energy += current_spin * saved_spin;
        }
    }
    return energy;
}

int color_span(const std::vector<int>& color) {
    if (color.empty()) {
        return 0;
    }
    return *std::max_element(color.begin(), color.end()) + 1;
}

int used_colors(const std::vector<int>& color) {
    std::vector<uint8_t> seen(static_cast<size_t>(color_span(color)), 0);
    for (const int c : color) {
        seen[static_cast<size_t>(c)] = 1;
    }
    return static_cast<int>(
        std::count(seen.begin(), seen.end(), static_cast<uint8_t>(1)));
}

int64_t exact_phi_from_coloring(const std::vector<int>& color) {
    std::vector<int> sizes(static_cast<size_t>(color_span(color)), 0);
    for (const int c : color) {
        ++sizes[static_cast<size_t>(c)];
    }
    return exact_phi_from_sizes(std::move(sizes));
}

} // namespace sumsearch
