# UCI launchers

Tiny shell wrappers that launch each of the eight registered engines
in **UCI mode** so they can be plugged into any UCI-compatible chess
GUI ([Cute Chess](https://github.com/cutechess/cutechess),
[Arena GUI](http://www.playwitharena.de/),
[Banksia GUI](https://banksiagui.com/), etc.).

These are *not* used by the framework itself — `arena/`, the contract
test suite, and the champion runners all spawn engines via the canonical
commands recorded in `arena/engines.py::REGISTRY`. These scripts exist
purely as convenience entry points for external GUIs that want a single
executable per engine.

## Files

| script               | engine                              |
|----------------------|-------------------------------------|
| `chainofthought.sh`  | `engines/chainofthought/`           |
| `contextualized.sh`  | `engines/oneshot_contextualized/`   |
| `debate.sh`          | `engines/debate/`                   |
| `ensemble.sh`        | `engines/ensemble/`                 |
| `langgraph.sh`       | `engines/langgraph/`                |
| `nocontext.sh`       | `engines/oneshot_nocontext/`        |
| `oneshot_react.sh`   | `engines/oneshot_react/`            |
| `rlm.sh`             | `engines/rlm/`                      |
| `pointchess.sh`      | alias for `nocontext.sh` (default) |

## Portability

Each script:

1. Resolves the repo root from its own location (`$(dirname "$0")/../..`),
   so it works no matter where the repo is cloned.
2. Uses `${POINTCHESS_PYTHON:-python3}` for the interpreter, so you can
   point at a specific Python without editing the file:

   ```bash
   POINTCHESS_PYTHON=/path/to/python3.11 \
       /full/path/to/infra/uci_launchers/chainofthought.sh
   ```

3. Runs under `set -euo pipefail` so a misconfigured launch fails loudly
   rather than silently degrading.

## Registering with a UCI GUI

Just point the GUI's "engine path" at the absolute path of the desired
`.sh` file. The GUI will spawn the script and speak UCI on its
stdin/stdout.
