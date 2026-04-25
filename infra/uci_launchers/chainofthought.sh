#!/usr/bin/env bash
# UCI launcher for the chainofthought engine. Suitable for plugging into
# Cute Chess / Arena GUI / Banksia / any UCI front-end. Override the
# Python interpreter with POINTCHESS_PYTHON.
set -euo pipefail
cd "$(dirname "$0")/../.."
exec "${POINTCHESS_PYTHON:-python3}" -m engines.chainofthought --uci
