"""LLM access layer.

Every agent goes through this module. Two design goals:

1. **One switch.** ``llm_mode()`` decides whether agents call a real LLM
   (OpenAI / Anthropic) or run a deterministic heuristic ("mock") path. This
   guarantees the whole graph runs end-to-end with no API keys, which protects
   the live demo and makes the evaluation harness reproducible.

2. **Structured output everywhere.** ``structured()`` always returns a validated
   Pydantic object, satisfying the "structured outputs at every handoff"
   requirement. Providers expose this via ``with_structured_output``.

Agents call ``structured(...)`` inside a try/except and fall back to their own
heuristic implementation if the call fails or we are in mock mode. That keeps a
single, debuggable contract for every agent boundary.
"""
from __future__ import annotations

from typing import Type, TypeVar

from pydantic import BaseModel

from config import settings

T = TypeVar("T", bound=BaseModel)


def llm_mode() -> str:
    """Return the active mode: ``"openai"``, ``"anthropic"`` or ``"mock"``."""
    if settings.force_mock:
        return "mock"
    if settings.provider == "openai" and settings.openai_api_key:
        return "openai"
    if settings.provider == "anthropic" and settings.anthropic_api_key:
        return "anthropic"
    return "mock"


def is_live() -> bool:
    """True when a real LLM is wired up."""
    return llm_mode() != "mock"


def structured(system: str, user: str, schema: Type[T]) -> T:
    """Call the active LLM and return a validated instance of ``schema``.

    Raises ``RuntimeError`` in mock mode so callers fall back to heuristics.
    """
    mode = llm_mode()

    if mode == "openai":
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0,
            api_key=settings.openai_api_key,
        )
        return llm.with_structured_output(schema).invoke(
            [("system", system), ("human", user)]
        )

    if mode == "anthropic":
        from langchain_anthropic import ChatAnthropic

        llm = ChatAnthropic(
            model=settings.anthropic_model,
            temperature=0,
            api_key=settings.anthropic_api_key,
        )
        return llm.with_structured_output(schema).invoke(
            [("system", system), ("human", user)]
        )

    raise RuntimeError("LLM unavailable (mock mode) — use the heuristic fallback")
