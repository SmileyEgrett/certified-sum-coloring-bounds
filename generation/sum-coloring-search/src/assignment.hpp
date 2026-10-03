// Adapter to SciPy's rectangular assignment implementation.
#pragma once
#include <cstddef>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <vector>
#include "../third_party/scipy/rectangular_lsap.h"

namespace sumsearch {
inline int maximum_assignment_weight(const std::vector<std::vector<int>>& weights) {
    const std::size_t n = weights.size();
    if (n == 0) return 0;
    if (n > 10000) throw std::runtime_error("assignment dimension exceeds supported limit");
    std::vector<double> costs;
    costs.reserve(n * n);
    int64_t total_weight = 0;
    for (const auto& row : weights) {
        if (row.size() != n) throw std::runtime_error("assignment must be square");
        for (const int w : row) {
            if (w < 0) throw std::runtime_error("negative overlap count");
            total_weight += w;
            costs.push_back(static_cast<double>(w));
        }
    }
    if (total_weight > std::numeric_limits<int>::max())
        throw std::runtime_error("overlap total exceeds supported range");
    std::vector<int64_t> rows(n), columns(n);
    const int status = solve_rectangular_linear_sum_assignment(
        static_cast<intptr_t>(n), static_cast<intptr_t>(n), costs.data(), true,
        rows.data(), columns.data());
    if (status != 0) throw std::runtime_error("assignment solver failed");
    std::vector<bool> row_seen(n, false), col_seen(n, false);
    int64_t weight = 0;
    for (std::size_t i = 0; i < n; ++i) {
        const int64_t r = rows[i], c = columns[i];
        if (r < 0 || c < 0 || r >= static_cast<int64_t>(n) ||
            c >= static_cast<int64_t>(n) || row_seen[r] || col_seen[c])
            throw std::runtime_error("invalid assignment returned by solver");
        row_seen[r] = col_seen[c] = true;
        weight += weights[r][c];
    }
    return static_cast<int>(weight);
}
} // namespace sumsearch
