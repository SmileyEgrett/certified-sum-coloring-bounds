#pragma once
#include "core.hpp"
#include <cerrno>
#include <charconv>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <iomanip>
#include <iostream>

namespace sumsearch {
struct Options {
    std::string graph_path, initial_coloring_path, save_best_path;
    int replicas = 20, threads = 1, size_factor = 8, report = 1;
    int64_t sweeps = 0;
    uint64_t seed = 1;
    double temperature = 0.6, gamma = 0.65;
    int plain_sa = 0, verify = 0, runway_slots = 0;
    std::string legal_repair = "auto", kick_operator = "none", edge_count = "edges";
    int kick_collapse = 0, kick_distance = -1, kick_stagnation = 0;
    int kick_empty = 0, kick_size = 1, kick_max_size = 32;
};

template<class T> T integer_option(const std::string& s) {
    T value{};
    const auto result = std::from_chars(s.data(), s.data() + s.size(), value);
    if (result.ec != std::errc{} || result.ptr != s.data() + s.size())
        die("invalid integer: " + s);
    return value;
}

inline double real_option(const std::string& s) {
    char* end = nullptr;
    errno = 0;
    double value = std::strtod(s.c_str(), &end);
    if (errno || end == s.c_str() || *end || !std::isfinite(value))
        die("invalid real number: " + s);
    return value;
}

inline void usage() {
    std::cout <<
        "sum_coloring --graph FILE --sweeps N --save-best FILE [options]\n"
        "  --initial-coloring FILE   proper starting assignment; otherwise random greedy\n"
        "  --plain-sa 0|1            population coupling (0, default) or independent SA (1)\n"
        "  --replicas N --threads N  defaults 20 replicas, one worker\n"
        "  --temperature T --gamma G defaults 0.6 and 0.65; positive values\n"
        "  --seed N --size-factor N  defaults 1 and 8\n"
        "  --legal-repair auto|scalar|bitset\n"
        "  --edge-count edges|incidences  DIMACS header convention (default edges)\n"
        "  --report N --verify 0|1   report interval and expensive internal checks\n"
        "  --runway-slots N          additional capacity for restart splits (default 0)\n"
        "  --kick-operator none|runway\n"
        "  --kick-collapse 0|1 --kick-distance N  default distance n/40\n"
        "  --kick-stagnation N --kick-empty 0|1   default disabled\n"
        "  --kick-size N --kick-max-size N       defaults 1 and 32\n"
        "N sweeps must be positive and finite. No work is launched by --help.\n";
}

inline Options parse_options(int argc, char** argv) {
    Options o;
    for (int i = 1; i < argc; ++i) {
        const std::string key = argv[i];
        if (key == "--help") { usage(); std::exit(0); }
        if (i + 1 == argc) die("missing value for " + key);
        const std::string value = argv[++i];
        if (key == "--graph") o.graph_path = value;
        else if (key == "--initial-coloring") o.initial_coloring_path = value;
        else if (key == "--save-best") o.save_best_path = value;
        else if (key == "--legal-repair") o.legal_repair = value;
        else if (key == "--kick-operator") o.kick_operator = value;
        else if (key == "--edge-count") o.edge_count = value;
        else if (key == "--temperature") o.temperature = real_option(value);
        else if (key == "--gamma") o.gamma = real_option(value);
        else if (key == "--seed") o.seed = integer_option<uint64_t>(value);
        else if (key == "--sweeps") o.sweeps = integer_option<int64_t>(value);
        else {
            const int n = integer_option<int>(value);
            if (key == "--replicas") o.replicas = n;
            else if (key == "--threads") o.threads = n;
            else if (key == "--size-factor") o.size_factor = n;
            else if (key == "--report") o.report = n;
            else if (key == "--plain-sa") o.plain_sa = n;
            else if (key == "--verify") o.verify = n;
            else if (key == "--runway-slots") o.runway_slots = n;
            else if (key == "--kick-collapse") o.kick_collapse = n;
            else if (key == "--kick-distance") o.kick_distance = n;
            else if (key == "--kick-stagnation") o.kick_stagnation = n;
            else if (key == "--kick-empty") o.kick_empty = n;
            else if (key == "--kick-size") o.kick_size = n;
            else if (key == "--kick-max-size") o.kick_max_size = n;
            else die("unknown option: " + key);
        }
    }
    if (o.graph_path.empty() || o.save_best_path.empty()) die("--graph and --save-best are required");
    if (o.sweeps <= 0 || o.sweeps == std::numeric_limits<int64_t>::max()) die("--sweeps must be positive and finite");
    if (o.replicas <= 0 || o.threads <= 0 || o.threads > o.replicas || o.size_factor <= 0 || o.report <= 0)
        die("invalid replica, worker, size-factor or report count");
    if ((!o.plain_sa || o.kick_collapse) && o.replicas < 2)
        die("population coupling and collapse restarts require at least two replicas");
    if (o.temperature <= 0 || o.gamma <= 0) die("temperature and gamma must be positive");
    for (int b : {o.plain_sa, o.verify, o.kick_collapse, o.kick_empty})
        if (b != 0 && b != 1) die("Boolean options take 0 or 1");
    if (o.runway_slots < 0 || o.kick_distance < -1 || o.kick_stagnation < 0 ||
        o.kick_size <= 0 || o.kick_max_size < o.kick_size) die("invalid restart setting");
    if (o.legal_repair != "auto" && o.legal_repair != "scalar" && o.legal_repair != "bitset")
        die("legal-repair must be auto, scalar or bitset");
    if (o.edge_count != "edges" && o.edge_count != "incidences")
        die("edge-count must be edges or incidences");
    if (o.kick_operator != "none" && o.kick_operator != "runway") die("unknown restart operator");
    const bool triggers = o.kick_collapse || o.kick_empty || o.kick_stagnation;
    if (triggers != (o.kick_operator == "runway")) die("runway restarts require at least one trigger, and vice versa");
    if (triggers && o.runway_slots == 0) die("runway restarts require positive runway-slots");
#ifndef _OPENMP
    if (o.threads != 1) die("this build supports one worker; enable OpenMP to use more");
#endif
    for (const std::string& path : {o.save_best_path, o.save_best_path + ".tmp"}) {
        if (std::filesystem::exists(path)) die("output already exists: " + path);
        if (std::filesystem::absolute(path).lexically_normal() == std::filesystem::absolute(o.graph_path).lexically_normal() ||
            (!o.initial_coloring_path.empty() && std::filesystem::absolute(path).lexically_normal() ==
             std::filesystem::absolute(o.initial_coloring_path).lexically_normal())) die("output overlaps an input");
    }
    return o;
}

inline Graph read_dimacs(const std::string& path, bool incidence_count = false) {
    std::ifstream in(path);
    if (!in) die("cannot open graph: " + path);
    Graph graph;
    int declared = -1;
    std::vector<std::pair<int, int>> edges;
    std::string line;
    while (std::getline(in, line)) {
        std::istringstream row(line);
        std::string tag, extra;
        if (!(row >> tag) || tag == "c" || tag == "C") continue;
        if (tag == "p" || tag == "P") {
            std::string kind;
            if (declared >= 0 || !(row >> kind >> graph.n >> declared) || (row >> extra) ||
                (kind != "edge" && kind != "col") || graph.n <= 0 || graph.n > 10000 || declared < 0 ||
                declared > static_cast<int64_t>(graph.n) * (graph.n - 1) / (incidence_count ? 1 : 2) ||
                (incidence_count && declared % 2 != 0))
                die("invalid DIMACS problem line (supported vertex count: 1..10000)");
        } else if (tag == "e" || tag == "E") {
            int u, v;
            if (declared < 0 || !(row >> u >> v) || (row >> extra) ||
                u <= 0 || v <= 0 || u > graph.n || v > graph.n || u == v) die("invalid DIMACS edge");
            if (u > v) std::swap(u, v);
            edges.emplace_back(u - 1, v - 1);
        } else die("unknown DIMACS record: " + tag);
    }
    if (!in.eof() || declared < 0 || edges.size() != static_cast<size_t>(declared / (incidence_count ? 2 : 1)))
        die("incomplete graph or declared edge count mismatch");
    std::sort(edges.begin(), edges.end());
    if (std::adjacent_find(edges.begin(), edges.end()) != edges.end()) die("duplicate graph edge");
    graph.m = static_cast<int>(edges.size());
    graph.adj.resize(graph.n);
    for (auto [u, v] : edges) { graph.adj[u].push_back(v); graph.adj[v].push_back(u); }
    return graph;
}

inline void write_coloring(const Options& opt, const Graph& graph,
                           const std::string& backend, const std::vector<int>& color,
                           int64_t phi) {
    if (color.size() != static_cast<size_t>(graph.n) || exact_conflicts(graph, color) ||
        exact_phi_from_coloring(color) != phi) die("invalid best coloring");
    const int span = color_span(color);
    std::vector<int> sizes(span, 0), order;
    for (int c : color) ++sizes[c];
    for (int c = 0; c < span; ++c) if (sizes[c]) order.push_back(c);
    std::sort(order.begin(), order.end(), [&](int a, int b) {
        return sizes[a] != sizes[b] ? sizes[a] > sizes[b] : a < b;
    });
    std::vector<int> canonical(span, 0);
    for (size_t i = 0; i < order.size(); ++i) canonical[order[i]] = static_cast<int>(i + 1);
    const std::string tmp = opt.save_best_path + ".tmp";
    std::ofstream out(tmp, std::ios::trunc);
    if (!out) die("cannot write checkpoint: " + tmp);
    out << std::setprecision(17)
        << "c minimum-sum coloring\nc graph " << std::filesystem::path(opt.graph_path).filename().string()
        << "\nc n " << graph.n << "\nc m " << graph.m
        << "\nc colors_used " << order.size() << "\nc canonical_sum " << phi
        << "\nc seed " << opt.seed << "\nc replicas " << opt.replicas
        << "\nc temperature " << opt.temperature << "\nc gamma " << opt.gamma
        << "\nc plain_sa " << opt.plain_sa << "\nc legal_repair " << backend
        << "\nc vertices and colors are 1-based\n";
    for (int v = 0; v < graph.n; ++v) out << v + 1 << ' ' << canonical[color[v]] << '\n';
    out.close();
    if (!out) die("checkpoint write failed: " + tmp);
    if (std::rename(tmp.c_str(), opt.save_best_path.c_str()) != 0) die("checkpoint rename failed");
}
} // namespace sumsearch
