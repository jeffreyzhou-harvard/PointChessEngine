"""Run the proposal -> critique -> verdict loop for every topic.

The advisors run in parallel within a phase using a small thread pool;
between phases we synchronise so each round can feed off the previous
one's transcripts.
"""
from __future__ import annotations

import concurrent.futures as _cf
import time
from dataclasses import dataclass, field
from typing import Callable

from methodologies.debate.prompts import (
    TOPICS,
    critique_prompt,
    proposal_prompt,
    verdict_prompt,
)
from methodologies.debate.providers import PROVIDERS, chat, have_key


@dataclass
class Advisor:
    provider: str        # key in PROVIDERS
    model: str           # provider-specific model id
    label: str           # human-readable name shown to others


@dataclass
class TopicResult:
    topic: dict
    proposals: dict[str, str] = field(default_factory=dict)   # advisor.label -> text
    critiques: dict[str, str] = field(default_factory=dict)
    verdict: str = ""


@dataclass
class CouncilResult:
    topics: list[TopicResult] = field(default_factory=list)
    advisors_used: list[str] = field(default_factory=list)
    lead_label: str = ""
    timings: dict[str, float] = field(default_factory=dict)


def default_advisors() -> list[Advisor]:
    """Build the default advisor lineup, skipping providers whose key is missing."""
    out: list[Advisor] = []
    for pname in ("openai", "xai", "gemini", "deepseek", "moonshot"):
        if not have_key(pname):
            continue
        info = PROVIDERS[pname]
        out.append(Advisor(provider=pname, model=info.default_model, label=info.label))
    return out


def _run_parallel(jobs: list[Callable[[], tuple[str, str]]],
                  max_workers: int = 5) -> dict[str, str]:
    """Run a batch of (label, text) producers in parallel; return label -> text."""
    out: dict[str, str] = {}
    with _cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(j) for j in jobs]
        for fut in _cf.as_completed(futures):
            try:
                label, text = fut.result()
            except Exception as exc:
                # We don't know which advisor failed without more bookkeeping;
                # caller wraps each job so it can self-identify in the error.
                # Record the error string keyed by a synthetic label.
                out[f"<error:{type(exc).__name__}>"] = str(exc)
                continue
            out[label] = text
    return out


def run_council(
    advisors: list[Advisor] | None = None,
    lead_provider: str = "anthropic",
    lead_model: str | None = None,
    log: Callable[[str], None] | None = None,
) -> CouncilResult:
    """Run the full council debate and return per-topic verdicts."""
    advisors = advisors or default_advisors()
    if not advisors:
        raise RuntimeError(
            "no advisor API keys found - set at least one of "
            "OPENAI_API_KEY, XAI_API_KEY, GEMINI_API_KEY, "
            "DEEPSEEK_API_KEY, MOONSHOT_API_KEY"
        )
    if not have_key(lead_provider):
        raise RuntimeError(
            f"lead provider {lead_provider!r} has no API key set"
        )
    lead_model = lead_model or PROVIDERS[lead_provider].default_model
    lead_label = PROVIDERS[lead_provider].label
    log = log or (lambda msg: None)

    result = CouncilResult(
        advisors_used=[a.label for a in advisors],
        lead_label=lead_label,
    )

    for topic in TOPICS:
        log(f"  topic: {topic['title']}")
        tr = TopicResult(topic=topic)
        # ---------- proposal phase ---------- #
        t0 = time.time()
        prop_jobs: list[Callable[[], tuple[str, str]]] = []
        for adv in advisors:
            sys_msg, user_msg = proposal_prompt(topic, adv.label)
            adv_local = adv  # capture
            def _job(adv=adv_local, s=sys_msg, u=user_msg):
                try:
                    txt = chat(adv.provider, adv.model, s, u, max_tokens=900)
                    return adv.label, txt
                except Exception as exc:
                    return adv.label, f"[ERROR from {adv.label}: {exc}]"
            prop_jobs.append(_job)
        tr.proposals = _run_parallel(prop_jobs, max_workers=len(advisors))
        log(f"    proposals: {len(tr.proposals)} ({time.time()-t0:.1f}s)")

        # ---------- critique phase ---------- #
        t0 = time.time()
        crit_jobs: list[Callable[[], tuple[str, str]]] = []
        for adv in advisors:
            own = tr.proposals.get(adv.label, "")
            others = [(label, text) for label, text in tr.proposals.items()
                      if label != adv.label]
            sys_msg, user_msg = critique_prompt(topic, adv.label, own, others)
            adv_local = adv
            def _job(adv=adv_local, s=sys_msg, u=user_msg):
                try:
                    txt = chat(adv.provider, adv.model, s, u, max_tokens=700)
                    return adv.label, txt
                except Exception as exc:
                    return adv.label, f"[ERROR from {adv.label}: {exc}]"
            crit_jobs.append(_job)
        tr.critiques = _run_parallel(crit_jobs, max_workers=len(advisors))
        log(f"    critiques: {len(tr.critiques)} ({time.time()-t0:.1f}s)")

        # ---------- verdict (lead, sequential) ---------- #
        t0 = time.time()
        transcript = _format_transcript(tr.proposals, tr.critiques)
        sys_msg, user_msg = verdict_prompt(topic, transcript)
        tr.verdict = chat(lead_provider, lead_model, sys_msg, user_msg,
                          max_tokens=1400, temperature=0.2)
        log(f"    verdict by {lead_label} ({time.time()-t0:.1f}s)")
        result.topics.append(tr)

    return result


def _format_transcript(proposals: dict[str, str],
                       critiques: dict[str, str]) -> str:
    parts: list[str] = []
    parts.append("# Proposal phase\n")
    for label, text in proposals.items():
        parts.append(f"## {label}\n{text}\n")
    parts.append("# Critique phase\n")
    for label, text in critiques.items():
        parts.append(f"## {label}\n{text}\n")
    return "\n".join(parts)


def render_design_contract(result: CouncilResult) -> str:
    """Glue all topic verdicts into one binding markdown document."""
    out: list[str] = []
    out.append("# Design contract")
    out.append("")
    out.append(f"Lead architect: **{result.lead_label}**")
    out.append(f"Advisors: {', '.join(result.advisors_used)}")
    out.append("")
    for tr in result.topics:
        out.append(f"## Topic: {tr.topic['title']}")
        out.append("")
        out.append(f"_{tr.topic['question']}_")
        out.append("")
        out.append(tr.verdict.strip())
        out.append("")
    return "\n".join(out)


def render_full_transcript(result: CouncilResult) -> str:
    """Full debate (proposals + critiques + verdicts), for the run record."""
    out: list[str] = []
    out.append("# Council debate transcript")
    out.append("")
    out.append(f"Lead: {result.lead_label}; advisors: {', '.join(result.advisors_used)}")
    out.append("")
    for tr in result.topics:
        out.append(f"# {tr.topic['title']}")
        out.append("")
        out.append(f"> {tr.topic['question']}")
        out.append("")
        out.append("## Proposals")
        for label, text in tr.proposals.items():
            out.append(f"### {label}")
            out.append(text)
            out.append("")
        out.append("## Critiques")
        for label, text in tr.critiques.items():
            out.append(f"### {label}")
            out.append(text)
            out.append("")
        out.append(f"## Verdict ({result.lead_label})")
        out.append(tr.verdict)
        out.append("")
    return "\n".join(out)
