"""Central configuration for ContractGuard.

All runtime knobs are read from environment variables (loaded from a local
``.env`` file if present). The system is designed to run with *zero* keys in a
deterministic MOCK mode; supplying an API key flips the agents to a real LLM.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional
    pass


def _flag(name: str, default: str = "") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    # LLM provider selection
    provider: str = os.getenv("LLM_PROVIDER", "openai").strip().lower()

    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY") or None
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY") or None
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

    # Force deterministic mock mode even if a key is present.
    force_mock: bool = _flag("CONTRACTGUARD_MOCK")

    # Risk routing thresholds (overall risk score, 0-100).
    high_risk_threshold: int = int(os.getenv("HIGH_RISK_THRESHOLD", "60"))
    low_risk_threshold: int = int(os.getenv("LOW_RISK_THRESHOLD", "25"))


settings = Settings()
