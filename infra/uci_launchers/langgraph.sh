#!/usr/bin/env bash
# UCI launcher for the langgraph engine.
set -euo pipefail
cd "$(dirname "$0")/../../engines/langgraph"
exec "${POINTCHESS_PYTHON:-python3}" -m uci.main
