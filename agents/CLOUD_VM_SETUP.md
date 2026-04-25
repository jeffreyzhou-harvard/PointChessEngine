# Cloud VM Setup

Cloud VM execution is optional. The recommended MVP is local Champion mode with git worktrees; see `agents/LOCAL_CHAMPION_SETUP.md`.

The selected stretch infrastructure for later reproducible runs is:

```text
GitHub repo
   |
   |-- Codex / Claude / Replit Agent / Cursor create candidate branches
   |
Ubuntu VM
   |
   |-- pulls repo
   |-- creates git worktrees
   |-- runs champion-stage script
   |-- runs tests/perft/UCI checks
   |-- runs FastChess tournaments when available
   |-- writes reports
   |-- promotes winning candidate
   |
Replit
   |
   |-- optional web UI / dashboard / final demo later
```

For now, Replit/UI is deferred. The core MVP orchestration is local worktrees. The Ubuntu VM can be added later as a neutral evaluator.

## VM Requirements

Use Ubuntu 22.04 or 24.04.

Install:

- git
- python3
- venv
- pip
- node/npm if needed
- tmux
- build-essential
- curl
- unzip
- stockfish if available
- FastChess optional
- GitHub auth
- `.env` for model keys if automated model calls are added later

## Example Setup

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip nodejs npm tmux build-essential curl unzip stockfish
```

Clone the repo:

```bash
git clone https://github.com/jeffreyzhou-harvard/PointChessEngine.git
cd PointChessEngine
```

Create a Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Authenticate GitHub:

```bash
gh auth login
```

Create worktrees:

```bash
mkdir -p ../worktrees
git worktree add ../worktrees/C3-react -b experiments/C3/react main
git worktree add ../worktrees/C3-debate -b experiments/C3/debate main
git worktree add ../worktrees/C3-gstack -b experiments/C3/gstack main
```

Run a Champion-stage evaluation:

```bash
python scripts/run_champion_stage.py --task C3_STATIC_EVALUATION --config configs/champion/C3_STATIC_EVALUATION.yaml.example
```

## VM Flow

The VM flow uses manual candidate branches created by Codex, Claude, Replit, Cursor, or other agent tools.

The VM evaluates candidates:

1. Pull repo.
2. Create worktrees.
3. Run tests/evals.
4. Score candidates.
5. Write comparison report.
6. Promote only with explicit confirmation.

Later automation can call model APIs directly. Replit remains optional UI/dashboard infrastructure, not core orchestration.
