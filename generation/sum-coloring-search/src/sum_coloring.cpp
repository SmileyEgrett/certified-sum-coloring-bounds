#include "io.hpp"
#include <chrono>
#include <csignal>
#include <exception>

namespace {
using namespace sumsearch;
volatile std::sig_atomic_t stop_requested = 0;
void request_stop(int) { stop_requested = 1; }

struct Stats {
    uint64_t proposed = 0, accepted = 0, improving_accepted = 0;
    uint64_t adjacent_zero = 0, kinetic_bound_rejected = 0;
    uint64_t kinetic_exact_evaluated = 0, empty_candidate_breaks = 0;
    void add(const Stats& s) {
        proposed += s.proposed; accepted += s.accepted;
        improving_accepted += s.improving_accepted; adjacent_zero += s.adjacent_zero;
        kinetic_bound_rejected += s.kinetic_bound_rejected;
        kinetic_exact_evaluated += s.kinetic_exact_evaluated;
        empty_candidate_breaks += s.empty_candidate_breaks;
    }
};
struct SweepResult {
    Stats stats;
    int64_t best_phi = std::numeric_limits<int64_t>::max();
    std::vector<int> best_color;
};

SweepResult search_sweep(const Graph& graph, const BitGraph& bits, const Options& opt,
                         bool bitset, const AcceptanceLookup& acceptance,
                         ReplicaState& state, Xoshiro256StarStar& stream,
                         int64_t previous_best, const std::vector<std::vector<int>>& saved,
                         const std::vector<int>& saved_slots, int replica) {
    Xoshiro256StarStar rng = stream;
    SweepResult result;
    int64_t local_best = previous_best;
    std::vector<FrozenOverlap> overlaps;
    if (!opt.plain_sa) {
        overlaps.resize(2);
        const int back = replica == 0 ? opt.replicas - 1 : replica - 1;
        const int forward = replica + 1 == opt.replicas ? 0 : replica + 1;
        overlaps[0].build(state, saved[back], saved_slots[back]);
        overlaps[1].build(state, saved[forward], saved_slots[forward]);
    }
    LegalMoveSet scalar;
    StableBitsetLegalMoveSet dense;
    if (bitset) {
        dense.build(state, bits);
        if (opt.verify) dense.verify(state, bits);
    } else {
        scalar.build(state);
        if (opt.verify) scalar.verify(state);
    }
    const int64_t attempts = static_cast<int64_t>(opt.size_factor) * graph.n * state.slots;
    for (int64_t attempt = 0; attempt < attempts; ++attempt) {
        if (state.slots <= 1) break;
        if (bitset ? dense.empty() : scalar.empty()) {
            ++result.stats.empty_candidate_breaks;
            break;
        }
        ++result.stats.proposed;
        const auto [v, to] = bitset ? dense.sample(&rng) : scalar.sample(&rng);
        const int from = state.color[v];
        const int a = state.sum.size(from), b = state.sum.size(to);
        const int64_t delta_phi = state.sum.delta(from, to);
        if (a == b + 1) ++result.stats.adjacent_zero;
        if (opt.verify) {
            auto sizes = state.sum.sizes();
            --sizes[from]; ++sizes[to];
            if (exact_phi_from_sizes(sizes) - state.sum.phi() != delta_phi)
                die("canonical move delta mismatch");
        }
        // Faithful acceptance: any improvement in the sum is accepted directly.
        bool accept = delta_phi < 0;
        if (!accept) {
            const double random = rng.uniform_open01();
            if (!opt.plain_sa && delta_phi > 0) {
                const int64_t upper = favorable_kinetic_upper_bound(a, b);
                if (!acceptance.accepts(delta_phi, upper, random)) {
                    ++result.stats.kinetic_bound_rejected;
                    if (opt.verify) {
                        int64_t exact = 0;
                        for (const auto& overlap : overlaps) exact += overlap.delta(state, v, from, to);
                        if (exact > upper || acceptance.accepts(delta_phi, exact, random))
                            die("kinetic rejection mismatch");
                    }
                    continue;
                }
            }
            int64_t delta_ke = 0;
            if (!opt.plain_sa) {
                for (const auto& overlap : overlaps) delta_ke += overlap.delta(state, v, from, to);
                ++result.stats.kinetic_exact_evaluated;
            }
            if (opt.verify && !opt.plain_sa) {
                auto moved = state.color;
                moved[v] = to;
                int64_t exact = 0;
                for (const auto& overlap : overlaps)
                    exact += exact_neighbor_kinetic(moved, *overlap.saved_color) -
                             exact_neighbor_kinetic(state.color, *overlap.saved_color);
                if (exact != delta_ke) die("kinetic move delta mismatch");
            }
            accept = acceptance.accepts(delta_phi, delta_ke, random);
        }
        if (!accept) continue;
        for (auto& overlap : overlaps) overlap.apply(v, from, to);
        if (bitset) dense.apply_accepted_move(bits, &state, v, from, to, delta_phi);
        else scalar.apply_accepted_move(graph, &state, v, from, to, delta_phi);
        ++result.stats.accepted;
        if (delta_phi < 0) ++result.stats.improving_accepted;
        if (state.sum.phi() < local_best) {
            local_best = state.sum.phi();
            result.best_phi = local_best;
            result.best_color = state.color;
        }
        if (opt.verify) {
            if (bitset) { verify_state_without_adj(graph, state, &overlaps); dense.verify(state, bits); }
            else { verify_state(graph, state, &overlaps); scalar.verify(state); }
        }
    }
    if (bitset) state.rebuild_adj_color(graph);
    state.compact_colors();
    if (opt.verify) verify_state(graph, state);
    stream = rng;
    return result;
}
} // namespace

int main(int argc, char** argv) {
    try {
        const Options opt = parse_options(argc, argv);
        const Graph graph = read_dimacs(opt.graph_path, opt.edge_count == "incidences");
        std::vector<Xoshiro256StarStar> rngs;
        for (int p = 0; p < opt.replicas; ++p)
            rngs.emplace_back(opt.seed + 0x9E3779B97F4A7C15ULL * static_cast<uint64_t>(p + 1));
        std::vector<std::vector<int>> initial(opt.replicas);
        int capacity = 0;
        if (!opt.initial_coloring_path.empty()) {
            const auto coloring = read_initial_coloring(opt.initial_coloring_path, graph);
            capacity = color_span(coloring);
            std::fill(initial.begin(), initial.end(), coloring);
        } else {
            for (int p = 0; p < opt.replicas; ++p) {
                initial[p] = random_greedy_coloring(graph, &rngs[p]);
                capacity = std::max(capacity, color_span(initial[p]));
            }
        }
        if (opt.runway_slots > graph.n - capacity) die("runway capacity exceeds vertex count");
        capacity += opt.runway_slots;
        const bool bitset = opt.legal_repair == "bitset" ||
            (opt.legal_repair == "auto" && auto_prefers_bitset_repair(graph, capacity));
        const std::string backend = bitset ? "bitset" : "scalar";
        BitGraph bits;
        if (bitset) bits.build(graph);
        // Independent restart streams begin after greedy initialization.
        std::vector<Xoshiro256StarStar> kick_rngs = rngs;
        std::vector<ReplicaState> replicas(opt.replicas);
        std::vector<int64_t> replica_best(opt.replicas);
        int64_t best_phi = std::numeric_limits<int64_t>::max();
        std::vector<int> best_color;
        for (int p = 0; p < opt.replicas; ++p) {
            replicas[p].build(graph, initial[p], capacity);
            if (opt.verify) verify_state(graph, replicas[p]);
            replica_best[p] = replicas[p].sum.phi();
            if (replica_best[p] < best_phi) { best_phi = replica_best[p]; best_color = replicas[p].color; }
        }
        auto saved = initial;
        std::vector<int> saved_slots(opt.replicas);
        for (int p = 0; p < opt.replicas; ++p) saved_slots[p] = replicas[p].slots;
        const double qtemperature = opt.temperature / opt.replicas;
        const double jgamma = opt.plain_sa ? 0.0 :
            -(qtemperature / 2.0) * std::log(std::tanh(opt.gamma / (opt.replicas * qtemperature)));
        if (qtemperature <= 0 || !std::isfinite(jgamma) || !std::isfinite(jgamma / qtemperature))
            die("temperature/gamma outside numerical range");
        const AcceptanceLookup acceptance(graph.n, opt.temperature,
                                          opt.plain_sa ? 0.0 : jgamma / qtemperature);
        std::vector<int64_t> last_improvement(opt.replicas, 0), last_stagnation_kick(opt.replicas, 0);
        std::vector<int> collapse_streak(opt.replicas, 0), empty_streak(opt.replicas, 0), stagnation_level(opt.replicas, 0);
        Stats total;
        uint64_t kick_events = 0, kick_selected = 0, kick_applied = 0, kick_moved = 0;
        uint64_t collapse_triggers = 0, empty_triggers = 0, stagnation_triggers = 0;
        int64_t kick_delta = 0, completed = 0;
        std::signal(SIGINT, request_stop);
        std::signal(SIGTERM, request_stop);
        write_coloring(opt, graph, backend, best_color, best_phi);
        int64_t checkpoint_phi = best_phi;
        std::cout << std::setprecision(17)
            << "run_start n=" << graph.n << " m=" << graph.m << " seed=" << opt.seed
            << " replicas=" << opt.replicas << " threads=" << opt.threads
            << " plain_sa=" << opt.plain_sa << " temperature=" << opt.temperature
            << " gamma=" << opt.gamma << " sweeps=" << opt.sweeps << " size_factor=" << opt.size_factor
            << " legal_repair=" << backend << " acceptance=faithful initial_phi=" << best_phi
            << " edge_count=" << opt.edge_count
            << " runway_slots=" << opt.runway_slots << " kick_operator=" << opt.kick_operator
            << " kick_collapse=" << opt.kick_collapse << " kick_distance=" << opt.kick_distance
            << " kick_stagnation=" << opt.kick_stagnation << " kick_empty=" << opt.kick_empty
            << " kick_size=" << opt.kick_size << " kick_max_size=" << opt.kick_max_size
            << " verify=" << opt.verify << '\n' << std::flush;
        const auto started = std::chrono::steady_clock::now();
        for (int64_t sweep = 1; sweep <= opt.sweeps && !stop_requested; ++sweep) {
            std::vector<SweepResult> results(opt.replicas);
            std::vector<std::exception_ptr> errors(opt.replicas);
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(opt.threads)
#endif
            for (int p = 0; p < opt.replicas; ++p) {
                try {
                    results[p] = search_sweep(graph, bits, opt, bitset, acceptance, replicas[p],
                                              rngs[p], replica_best[p], saved, saved_slots, p);
                } catch (...) { errors[p] = std::current_exception(); }
            }
            for (const auto& error : errors) if (error) std::rethrow_exception(error);
            completed = sweep;
            for (int p = 0; p < opt.replicas; ++p) {
                total.add(results[p].stats);
                if (results[p].best_phi < replica_best[p]) {
                    replica_best[p] = results[p].best_phi;
                    last_improvement[p] = last_stagnation_kick[p] = sweep;
                    stagnation_level[p] = 0;
                }
                if (results[p].best_phi < best_phi) {
                    best_phi = results[p].best_phi; best_color = results[p].best_color;
                }
                if (replicas[p].sum.phi() < best_phi) {
                    best_phi = replicas[p].sum.phi(); best_color = replicas[p].color;
                }
            }
            std::vector<int> strength(opt.replicas, 0);
            if (opt.kick_operator == "runway" && !stop_requested && sweep != opt.sweeps) {
                const int threshold = opt.kick_distance < 0 ? graph.n / 40 : opt.kick_distance;
                for (int p = 0; p < opt.replicas; ++p) {
                    bool collapse = false;
                    if (opt.kick_collapse) {
                        const int back = p == 0 ? opt.replicas - 1 : p - 1;
                        const int forward = p + 1 == opt.replicas ? 0 : p + 1;
                        const int d1 = partition_distance(replicas[p].color, saved[back], capacity);
                        const int d2 = partition_distance(replicas[p].color, saved[forward], capacity);
                        collapse = d1 <= threshold || d2 <= threshold;
                    }
                    const bool empty = opt.kick_empty && results[p].stats.empty_candidate_breaks > 0;
                    const bool stagnant = opt.kick_stagnation > 0 &&
                        sweep - std::max(last_improvement[p], last_stagnation_kick[p]) >= opt.kick_stagnation;
                    // Saturating a level once the maximum kick size is reached
                    // leaves the selected strength unchanged and avoids overflow.
                    const auto increment = [&](int level) { return level < opt.kick_max_size ? level + 1 : level; };
                    collapse_streak[p] = collapse ? increment(collapse_streak[p]) : 0;
                    empty_streak[p] = empty ? increment(empty_streak[p]) : 0;
                    if (stagnant) { stagnation_level[p] = increment(stagnation_level[p]); last_stagnation_kick[p] = sweep; }
                    if (collapse || empty || stagnant) {
                        const int level = std::max({1, collapse_streak[p], empty_streak[p], stagnation_level[p]});
                        strength[p] = static_cast<int>(std::min<int64_t>(opt.kick_max_size,
                                                                      static_cast<int64_t>(opt.kick_size) * level));
                        collapse_triggers += collapse; empty_triggers += empty; stagnation_triggers += stagnant;
                    }
                }
            }
            // Freeze the completed search states before applying restarts.
            for (int p = 0; p < opt.replicas; ++p) {
                saved[p] = replicas[p].color; saved_slots[p] = replicas[p].slots;
            }
            bool kicked = false;
            for (int p = 0; p < opt.replicas; ++p) {
                if (!strength[p]) continue;
                kicked = true; ++kick_selected;
                int64_t delta = 0;
                const int moved = apply_runway_split(graph, &replicas[p], strength[p], &kick_rngs[p], &delta);
                if (moved) { ++kick_applied; kick_moved += moved; kick_delta += delta; }
                if (opt.verify) verify_state(graph, replicas[p]);
                if (replicas[p].sum.phi() < replica_best[p]) {
                    replica_best[p] = replicas[p].sum.phi();
                    last_improvement[p] = last_stagnation_kick[p] = sweep; stagnation_level[p] = 0;
                }
                if (replicas[p].sum.phi() < best_phi) { best_phi = replicas[p].sum.phi(); best_color = replicas[p].color; }
            }
            kick_events += kicked;
            if (best_phi < checkpoint_phi) {
                write_coloring(opt, graph, backend, best_color, best_phi); checkpoint_phi = best_phi;
            }
            if (sweep % opt.report == 0 || sweep == opt.sweeps || stop_requested)
                std::cout << "sweep=" << sweep << " best_phi=" << best_phi
                          << " proposed=" << total.proposed << " accepted=" << total.accepted
                          << " kick_events=" << kick_events << '\n' << std::flush;
        }
        write_coloring(opt, graph, backend, best_color, best_phi);
        std::cout << "final_sweep=" << completed << "\nstopped_by_signal=" << (stop_requested ? 1 : 0)
                  << "\nbest_phi=" << best_phi << "\nbest_colors_used=" << used_colors(best_color)
                  << "\nverified_best_conflicts=" << exact_conflicts(graph, best_color)
                  << "\nverified_best_phi=" << exact_phi_from_coloring(best_color)
                  << "\nproposed=" << total.proposed << "\naccepted=" << total.accepted
                  << "\nimproving_accepted=" << total.improving_accepted
                  << "\nadjacent_zero=" << total.adjacent_zero
                  << "\nkinetic_bound_rejected=" << total.kinetic_bound_rejected
                  << "\nkinetic_exact_evaluated=" << total.kinetic_exact_evaluated
                  << "\nempty_candidate_breaks=" << total.empty_candidate_breaks
                  << "\nkick_events=" << kick_events << "\nkick_selected_replicas=" << kick_selected
                  << "\nkick_applied=" << kick_applied << "\nkick_moved_vertices=" << kick_moved
                  << "\nkick_total_delta_phi=" << kick_delta << "\nkick_collapse_triggers=" << collapse_triggers
                  << "\nkick_stagnation_triggers=" << stagnation_triggers << "\nkick_empty_triggers=" << empty_triggers
                  << "\nwall_seconds=" << std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count()
                  << '\n';
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << '\n'; return 1;
    }
}
