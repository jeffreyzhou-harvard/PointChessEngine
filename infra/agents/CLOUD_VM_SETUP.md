# Cloud VM Setup

Cloud VM execution is optional. The recommended MVP is GitHub-hosted Dockerized Champion mode plus local Champion mode; see `infra/agents/LOCAL_CHAMPION_SETUP.md`.

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

For now, Replit/UI is deferred. The core MVP orchestration is Dockerized Champion mode on GitHub-hosted runners. The Ubuntu VM can be added later as a neutral self-hosted evaluator.

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
- Docker
- GitHub Actions self-hosted runner if using the VM as `champion-vm`
- `.env` for model keys if automated model calls are added later

## Example Setup

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip nodejs npm tmux build-essential curl unzip ca-certificates stockfish
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
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
python infra/scripts/run_champion_stage.py --task C3_STATIC_EVALUATION --config infra/configs/champion/C3_STATIC_EVALUATION.yaml.example
```

Run the current checked-in engines in parallel:

```bash
python infra/scripts/run_local_champion.py \
  --task CURRENT_ENGINES \
  --config infra/configs/champion/CURRENT_ENGINES.yaml \
  --jobs 6 \
  --skip-create-worktrees
```

Build and run the Dockerized Champion POC:

```bash
docker build -f infra/docker/Dockerfile.champion -t pointchess/champion:local .
docker run --rm -v "$PWD:/repo" -w /repo pointchess/champion:local \
  python infra/scripts/run_local_champion.py \
    --task CURRENT_ENGINES \
    --config infra/configs/champion/CURRENT_ENGINES.yaml \
    --jobs 6 \
    --skip-create-worktrees
```

## GitHub Actions Self-Hosted Runner

Only do this if you want the VM to appear as the `champion-vm` target in the
`Champion Current Engines` workflow.

1. In GitHub, open the repo settings.
2. Go to **Actions > Runners > New self-hosted runner**.
3. Choose Linux x64 or ARM64 to match the VM.
4. Follow GitHub's generated install commands on the VM.
5. Add this runner label:

```text
champion-vm
```

Run the workflow manually with:

```text
runner_target = champion-vm
```

The default `runner_target = github-hosted` requires no VM.

## VM Flow

The VM flow uses the same Docker image and Champion configs as GitHub-hosted Actions. Manual candidate branches can still be created by Codex, Claude, Replit, Cursor, or other agent tools.

The VM evaluates candidates:

1. Pull repo.
2. Create worktrees.
3. Run tests/evals.
4. Score candidates.
5. Write comparison report.
6. Promote only with explicit confirmation.

Later automation can call model APIs directly. Replit remains optional UI/dashboard infrastructure, not core orchestration.
