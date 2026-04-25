#!/usr/bin/env bash
# Default PointChess UCI launcher: routes to the oneshot_nocontext
# engine. Useful when a UCI front-end wants a single "pointchess"
# entry without choosing a specific methodology variant.
set -euo pipefail
cd "$(dirname "$0")/../.."
exec "${POINTCHESS_PYTHON:-python3}" -m engines.oneshot_nocontext --uci
