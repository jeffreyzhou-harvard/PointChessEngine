"""Pluggable LLM client layer.

All advisors hit OpenAI-compatible HTTP endpoints (OpenAI, xAI/Grok,
DeepSeek, Moonshot/Kimi, Gemini's openai-compat layer) so they share
one code path. The lead architect uses the Anthropic SDK directly
because the build phase needs Claude tool-use, which is provider-
specific.

Auth is via per-provider env vars (see :data:`PROVIDERS`). Missing keys
just mean that advisor is skipped at runtime - the council still
proceeds with whoever's available.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderInfo:
    name: str
    env_key: str
    base_url: str | None     # None => Anthropic / native SDK
    default_model: str
    label: str               # human-readable for logs / debate transcripts


PROVIDERS: dict[str, ProviderInfo] = {
    # OpenAI-compatible advisors --------------------------------------------
    "openai": ProviderInfo(
        name="openai", env_key="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4.1", label="OpenAI",
    ),
    "xai": ProviderInfo(
        name="xai", env_key="XAI_API_KEY",
        base_url="https://api.x.ai/v1",
        default_model="grok-4", label="Grok",
    ),
    "gemini": ProviderInfo(
        name="gemini", env_key="GEMINI_API_KEY",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        default_model="gemini-2.5-pro", label="Gemini",
    ),
    "deepseek": ProviderInfo(
        name="deepseek", env_key="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat", label="DeepSeek",
    ),
    "moonshot": ProviderInfo(
        name="moonshot", env_key="MOONSHOT_API_KEY",
        base_url="https://api.moonshot.ai/v1",
        default_model="kimi-k2-0905-preview", label="Kimi",
    ),
    # Lead architect (also tool-use capable) --------------------------------
    "anthropic": ProviderInfo(
        name="anthropic", env_key="ANTHROPIC_API_KEY",
        base_url=None,
        default_model="claude-opus-4-7", label="Claude",
    ),
}


def _anthropic_supports_temperature(model: str) -> bool:
    """Newer Claude models (4.7+) reject the `temperature` parameter."""
    m = model.lower()
    # Known to NOT accept temperature.
    if any(tag in m for tag in ("opus-4-7", "sonnet-4-7", "haiku-4-7")):
        return False
    # Default: pass it. If a future model also rejects it, the provider
    # error message is descriptive enough for the user to add a tag here.
    return True


def have_key(provider_name: str) -> bool:
    info = PROVIDERS[provider_name]
    return bool(os.environ.get(info.env_key) or os.environ.get(info.env_key.replace("_API_KEY", "_KEY")))


def _get_key(info: ProviderInfo) -> str:
    key = (
        os.environ.get(info.env_key)
        or os.environ.get(info.env_key.replace("_API_KEY", "_KEY"))
    )
    if not key:
        raise RuntimeError(f"missing env var: {info.env_key}")
    return key


def chat(
    provider_name: str,
    model: str,
    system: str,
    user: str,
    *,
    max_tokens: int = 2048,
    temperature: float = 0.4,
    retries: int = 2,
) -> str:
    """Single-shot non-tool chat for any OpenAI-compatible advisor.

    Returns the assistant's text reply. Raises on persistent failure.
    Anthropic is supported here too for symmetry (used when the lead
    needs a non-tool thinking pass).
    """
    info = PROVIDERS[provider_name]
    key = _get_key(info)
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            if info.base_url is None:
                # Anthropic native SDK. Newer Claude models reject `temperature`,
                # so we only pass it for older model ids that still accept it.
                import anthropic
                client = anthropic.Anthropic(api_key=key)
                kwargs: dict = dict(
                    model=model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                if _anthropic_supports_temperature(model):
                    kwargs["temperature"] = temperature
                msg = client.messages.create(**kwargs)
                # Concatenate text blocks.
                parts = [b.text for b in msg.content if getattr(b, "type", "") == "text"]
                return "\n".join(parts).strip()
            else:
                from openai import OpenAI
                client = OpenAI(api_key=key, base_url=info.base_url)
                resp = client.chat.completions.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                return (resp.choices[0].message.content or "").strip()
        except Exception as exc:  # broad: provider SDKs raise their own families
            last_exc = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"unreachable: {last_exc}")
