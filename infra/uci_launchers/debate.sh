#!/usr/bin/env bash
# UCI launcher for the debate engine.
set -euo pipefail
cd "$(dirname "$0")/../../engines/debate"
exec "${POINTCHESS_PYTHON:-python3}" main.py --uci
