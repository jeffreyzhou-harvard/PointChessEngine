"""CLI entry point: ``python -m methodologies.debate``.

Examples
--------
    # End-to-end with all available advisors + Claude as lead.
    python -m methodologies.debate

    # Custom output dir and a different lead model.
    python -m methodologies.debate --output ./out --lead-model claude-sonnet-4-6

    # Restrict advisors and override their default models.
    python -m methodologies.debate \\
        --advisor openai=gpt-4.1 --advisor xai=grok-4

    # Just produce the design contract; do not invoke the build.
    python -m methodologies.debate --skip-build

    # Larger build budget (default 60 iterations).
    python -m methodologies.debate --max-build-iterations 120
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from methodologies.debate.council import Advisor
from methodologies.debate.providers import PROVIDERS, have_key
from methodologies.debate.runner import (
    DEFAULT_OUTPUT_DIR,
    default_brief,
    run,
    summarize,
)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m methodologies.debate",
        description="Multi-model debate methodology for chess-engine design + build.",
    )
    p.add_argument("--output", default=DEFAULT_OUTPUT_DIR,
                   help="Output dir the build phase writes into.")
    p.add_argument("--lead-provider", default="anthropic",
                   help="Provider used for verdicts + the build phase (default: anthropic).")
    p.add_argument("--lead-model", default=None,
                   help="Override the lead provider's default model.")
    p.add_argument("--advisor", action="append", default=[],
                   help=("Force a specific advisor lineup. Format `name=model`. "
                         "Repeatable. Without --advisor we autodetect from env keys."))
    p.add_argument("--skip-build", action="store_true",
                   help="Stop after writing the design contract; don't invoke the build.")
    p.add_argument("--max-build-iterations", type=int, default=60,
                   help="Hard cap on Claude tool-use turns during the build.")
    p.add_argument("--list-providers", action="store_true",
                   help="Show known providers + which keys are present, then exit.")
    return p


def _parse_advisor_args(specs: list[str]) -> list[Advisor] | None:
    if not specs:
        return None
    out: list[Advisor] = []
    for spec in specs:
        if "=" not in spec:
            sys.stderr.write(f"--advisor expects name=model, got {spec!r}\n")
            sys.exit(2)
        name, model = spec.split("=", 1)
        name = name.strip()
        if name not in PROVIDERS or name == "anthropic":
            sys.stderr.write(
                f"unknown advisor provider {name!r}; "
                f"choose from: openai, xai, gemini, deepseek, moonshot\n"
            )
            sys.exit(2)
        info = PROVIDERS[name]
        out.append(Advisor(provider=name, model=model.strip(), label=info.label))
    return out


def _list_providers() -> int:
    print(f"{'provider':12s} {'env var':22s} {'default model':32s} key?")
    print("-" * 76)
    for name, info in PROVIDERS.items():
        kind = "lead" if name == "anthropic" else "advisor"
        present = "yes" if have_key(name) else "no"
        print(f"{name:12s} {info.env_key:22s} {info.default_model:32s} {present}  ({kind})")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.list_providers:
        return _list_providers()

    sys.stdout.write(f"[run] {default_brief()}\n")
    sys.stdout.write(f"[run] output_dir={args.output} lead={args.lead_provider}\n")

    advisors = _parse_advisor_args(args.advisor)
    result = run(
        output_dir=args.output,
        advisors=advisors,
        lead_provider=args.lead_provider,
        lead_model=args.lead_model,
        skip_build=args.skip_build,
        max_build_iterations=args.max_build_iterations,
        log=lambda m: sys.stdout.write(m + "\n"),
    )
    sys.stdout.write("\n=== run complete ===\n")
    sys.stdout.write(summarize(result) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
