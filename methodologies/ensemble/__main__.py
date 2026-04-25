"""CLI entry point: ``python -m methodologies.ensemble``.

Examples
--------

    # End-to-end with every voter whose API key is present (Claude is a
    # peer voter here, not a judge).
    python -m methodologies.ensemble

    # Only produce the design contract; skip the build phase.
    python -m methodologies.ensemble --skip-build

    # Override the builder model.
    python -m methodologies.ensemble --builder-model claude-sonnet-4-6

    # Restrict the voter lineup explicitly.
    python -m methodologies.ensemble \\
        --voter openai=gpt-4.1 --voter xai=grok-4 --voter gemini=gemini-2.5-pro

    # Inspect provider availability without spending tokens.
    python -m methodologies.ensemble --list-providers
"""
from __future__ import annotations

import argparse
import sys

from methodologies.ensemble.ballot import Voter
from methodologies.ensemble.providers import PROVIDERS, have_key
from methodologies.ensemble.runner import (
    DEFAULT_OUTPUT_DIR,
    default_brief,
    run,
    summarize,
)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m methodologies.ensemble",
        description="Multi-model VOTING methodology for chess-engine design + build (no judge).",
    )
    p.add_argument("--output", default=DEFAULT_OUTPUT_DIR,
                   help="Output dir the build phase writes into.")
    p.add_argument("--builder-provider", default="anthropic",
                   help="Provider used for the build phase (default: anthropic).")
    p.add_argument("--builder-model", default=None,
                   help="Override the builder provider's default model.")
    p.add_argument("--voter", action="append", default=[],
                   help=("Force a specific voter lineup. Format `name=model`. "
                         "Repeatable. Without --voter we autodetect from env keys."))
    p.add_argument("--skip-build", action="store_true",
                   help="Stop after writing the design contract; don't invoke the build.")
    p.add_argument("--max-build-iterations", type=int, default=60,
                   help="Hard cap on Claude tool-use turns during the build.")
    p.add_argument("--list-providers", action="store_true",
                   help="Show known providers + which keys are present, then exit.")
    return p


def _parse_voter_args(specs: list[str]) -> list[Voter] | None:
    if not specs:
        return None
    out: list[Voter] = []
    for spec in specs:
        if "=" not in spec:
            sys.stderr.write(f"--voter expects name=model, got {spec!r}\n")
            sys.exit(2)
        name, model = spec.split("=", 1)
        name = name.strip()
        if name not in PROVIDERS:
            sys.stderr.write(
                f"unknown voter provider {name!r}; "
                f"choose from: {', '.join(PROVIDERS)}\n"
            )
            sys.exit(2)
        info = PROVIDERS[name]
        out.append(Voter(provider=name, model=model.strip(), label=info.label))
    return out


def _list_providers() -> int:
    print(f"{'provider':12s} {'env var':22s} {'default model':32s} key?")
    print("-" * 76)
    for name, info in PROVIDERS.items():
        present = "yes" if have_key(name) else "no"
        # In ensemble methodology Claude is a peer voter, not a special role.
        kind = "voter" if name != "anthropic" else "voter (also default builder)"
        print(f"{name:12s} {info.env_key:22s} {info.default_model:32s} {present}  ({kind})")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.list_providers:
        return _list_providers()

    sys.stdout.write(f"[run] {default_brief()}\n")
    sys.stdout.write(f"[run] output_dir={args.output} builder={args.builder_provider}\n")

    voters = _parse_voter_args(args.voter)
    result = run(
        output_dir=args.output,
        voters=voters,
        builder_provider=args.builder_provider,
        builder_model=args.builder_model,
        skip_build=args.skip_build,
        max_build_iterations=args.max_build_iterations,
        log=lambda m: sys.stdout.write(m + "\n"),
    )
    sys.stdout.write("\n=== run complete ===\n")
    sys.stdout.write(summarize(result) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
