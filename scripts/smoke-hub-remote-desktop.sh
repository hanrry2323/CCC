#!/usr/bin/env bash
# 已废：勿以 2017 为 chat origin。转调双口烟测。
# 见 docs/product/hub-remote-management.md
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "WARN: smoke-hub-remote-desktop.sh deprecated → smoke-dual-port-remote.sh" >&2
exec bash "${ROOT}/scripts/smoke-dual-port-remote.sh" "$@"
