#!/usr/bin/env bash
# UCI launcher for the oneshot_contextualized engine.
set -euo pipefail
cd "$(dirname "$0")/../../engines/oneshot_contextualized"
exec "${POINTCHESS_PYTHON:-python3}" run_uci.py
