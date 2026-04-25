#!/usr/bin/env bash
# UCI launcher for the oneshot_react engine.
set -euo pipefail
cd "$(dirname "$0")/../.."
exec "${POINTCHESS_PYTHON:-python3}" -m engines.oneshot_react --uci
