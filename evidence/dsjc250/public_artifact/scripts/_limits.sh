#!/usr/bin/env bash
# Bounded defaults; callers may lower or raise explicitly through the environment.
CPU_LIMIT_SECONDS=${CPU_LIMIT_SECONDS:-180}
VIRTUAL_MEMORY_KB=${VIRTUAL_MEMORY_KB:-2097152}
ulimit -t "$CPU_LIMIT_SECONDS" 2>/dev/null || true
ulimit -v "$VIRTUAL_MEMORY_KB" 2>/dev/null || true
export PYTHONDONTWRITEBYTECODE=1
