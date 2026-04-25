#!/usr/bin/env bash
# UCI launcher for the rlm engine.
set -euo pipefail
cd "$(dirname "$0")/../.."
exec "${POINTCHESS_PYTHON:-python3}" -m engines.rlm --uci
