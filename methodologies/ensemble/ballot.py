"""Run the proposal -> vote loop for every topic.

Every advisor proposes (parallel within a phase), then every advisor
votes on every topic (also parallel). Topic winners are decided by
plurality. Self-votes are allowed - models are usually not unduly
biased toward their own writing, and forbidding self-votes introduces
a different bias.
"""
from __future__ import annotations

import concurrent.futures as _cf
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

from methodologies.ensemble.prompts import (
    TOPICS,
    parse_vote,
    proposal_prompt,
    vote_prompt,
)
from methodologies.ensemble.providers import PROVIDERS, chat, have_key


@dataclass
class Voter:
    """A single LLM voter (proposes AND votes; one persona, one ballot)."""
    provider: str
    model: str
    label: str


@dataclass
class TopicResult:
    topic: dict
    proposals: dict[str, str] = field(default_factory=dict)   # label -> text
    ballots:   dict[str, str | None] = field(default_factory=dict)  # voter -> chosen label
    tally:     dict[str, int] = field(default_factory=dict)   # label -> votes
    winner_label: str = ""
    winner_proposal: str = ""
    abstentions: list[str] = field(default_factory=list)      # voters whose vote couldn't be parsed


@dataclass
class EnsembleResult:
    topics: list[TopicResult] = field(default_factory=list)
    voters_used: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)


def default_voters() -> list[Voter]:
    """Auto-detect voter lineup from provider env keys.

    Includes Anthropic (Claude) as a peer voter - in the ensemble
    methodology Claude has no special judging role, so it sits at the
    same table as the advisors.
    """
    out: list[Voter] = []
    for pname in ("openai", "xai", "gemini", "deepseek", "moonshot", "anthropic"):
        if not have_key(pname):
            continue
        info = PROVIDERS[pname]
        out.append(Voter(provider=pname, model=info.default_model, label=info.label))
    return out


def _run_parallel(jobs: list[Callable[[], tuple[str, str]]],
                  max_workers: int = 6) -> dict[str, str]:
    """Run a batch of (label, text) producers in parallel; return label -> text."""
    out: dict[str, str] = {}
    if not jobs:
        return out
    with _cf.ThreadPoolExecutor(max_workers=min(max_workers, len(jobs))) as ex:
        for fut in _cf.as_completed([ex.submit(j) for j in jobs]):
            try:
                label, text = fut.result()
                out[label] = text
            except Exception as exc:
                out[f"<error:{type(exc).__name__}>"] = str(exc)
    return out


def run_ensemble(
    voters: list[Voter] | None = None,
    log: Callable[[str], None] | None = None,
) -> EnsembleResult:
    """Drive proposal + vote phases for every topic and return tallies."""
    voters = voters or default_voters()
    if len(voters) < 2:
        raise RuntimeError(
            "ensemble needs at least 2 voters - set 2+ provider API keys "
            "(OPENAI_API_KEY, XAI_API_KEY, GEMINI_API_KEY, "
            "DEEPSEEK_API_KEY, MOONSHOT_API_KEY, ANTHROPIC_API_KEY)"
        )
    log = log or (lambda _: None)
    result = EnsembleResult(voters_used=[v.label for v in voters])

    for topic in TOPICS:
        log(f"  topic: {topic['title']}")
        tr = TopicResult(topic=topic)

        # ---- proposal phase (parallel) ---- #
        t0 = time.time()
        prop_jobs: list[Callable[[], tuple[str, str]]] = []
        for v in voters:
            sys_msg, user_msg = proposal_prompt(topic, v.label)
            v_local = v
            def _job(v=v_local, s=sys_msg, u=user_msg):
                try:
                    txt = chat(v.provider, v.model, s, u, max_tokens=900)
                    return v.label, txt
                except Exception as exc:
                    return v.label, f"[ERROR from {v.label}: {exc}]"
            prop_jobs.append(_job)
        tr.proposals = _run_parallel(prop_jobs)
        log(f"    proposals: {len(tr.proposals)} ({time.time()-t0:.1f}s)")

        # ---- vote phase (parallel) ---- #
        t0 = time.time()
        candidates = list(tr.proposals.items())
        candidate_labels = [label for label, _ in candidates]
        ballot_jobs: list[Callable[[], tuple[str, str]]] = []
        for v in voters:
            sys_msg, user_msg = vote_prompt(topic, v.label, candidates)
            v_local = v
            def _job(v=v_local, s=sys_msg, u=user_msg):
                try:
                    txt = chat(v.provider, v.model, s, u, max_tokens=400)
                    return v.label, txt
                except Exception as exc:
                    return v.label, f"[ERROR from {v.label}: {exc}]"
            ballot_jobs.append(_job)
        ballot_texts = _run_parallel(ballot_jobs)

        # Parse + tally.
        tally: Counter[str] = Counter()
        for voter_label, text in ballot_texts.items():
            chosen = parse_vote(text, candidate_labels)
            tr.ballots[voter_label] = chosen
            if chosen is None:
                tr.abstentions.append(voter_label)
            else:
                tally[chosen] += 1
        tr.tally = dict(tally)
        log(f"    ballots:   {len(ballot_texts)} ({time.time()-t0:.1f}s); "
            f"tally={dict(tally)} abstentions={len(tr.abstentions)}")

        # ---- decide winner ---- #
        if tally:
            top_count = max(tally.values())
            tied = sorted(label for label, n in tally.items() if n == top_count)
            tr.winner_label = tied[0]  # alphabetical tiebreak (deterministic)
        else:
            # Total abstention - fall back to the first proposal (deterministic).
            tr.winner_label = candidate_labels[0] if candidate_labels else ""
        tr.winner_proposal = tr.proposals.get(tr.winner_label, "")
        log(f"    winner:    {tr.winner_label}")

        result.topics.append(tr)

    return result


def render_design_contract(result: EnsembleResult) -> str:
    """Glue the winning proposal per topic into one binding document."""
    out: list[str] = []
    out.append("# Design contract")
    out.append("")
    out.append(f"Voted into existence by: {', '.join(result.voters_used)}")
    out.append("")
    for tr in result.topics:
        out.append(f"## Topic: {tr.topic['title']}")
        out.append(f"_Question: {tr.topic['question']}_")
        out.append("")
        if tr.tally:
            tally_str = ", ".join(f"{k}:{v}" for k, v in
                                  sorted(tr.tally.items(), key=lambda x: -x[1]))
            out.append(f"_Tally: {tally_str}; winner: **{tr.winner_label}**_")
        else:
            out.append(f"_All voters abstained; default-pick: **{tr.winner_label}**_")
        out.append("")
        out.append(tr.winner_proposal.strip())
        out.append("")
    return "\n".join(out)


def render_full_transcript(result: EnsembleResult) -> str:
    """Full ballot record (proposals + per-voter ballots + tallies)."""
    out: list[str] = []
    out.append("# Ensemble ballot transcript")
    out.append("")
    out.append(f"Voters: {', '.join(result.voters_used)}")
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
        out.append("## Ballots")
        for voter, chosen in tr.ballots.items():
            verdict = chosen if chosen else "(unparseable / abstention)"
            out.append(f"- **{voter}** voted for: {verdict}")
        if tr.tally:
            tally_str = ", ".join(f"{k}:{v}" for k, v in
                                  sorted(tr.tally.items(), key=lambda x: -x[1]))
            out.append("")
            out.append(f"## Tally\n{tally_str}")
            out.append(f"\n**Winner: {tr.winner_label}**")
        out.append("")
    return "\n".join(out)
