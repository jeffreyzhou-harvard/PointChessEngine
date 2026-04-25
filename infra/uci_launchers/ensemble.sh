#!/usr/bin/env bash
# UCI launcher for the ensemble engine.
set -euo pipefail
cd "$(dirname "$0")/../../engines/ensemble"
exec "${POINTCHESS_PYTHON:-python3}" main.py --uci
