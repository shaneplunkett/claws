from __future__ import annotations

from . import claude, codex
from .base import Adapter

ADAPTERS: dict[str, Adapter] = {
    "claude": claude.ClaudeAdapter(),
    "codex": codex.CodexAdapter(),
}


def get(harness: str) -> Adapter:
    try:
        return ADAPTERS[harness]
    except KeyError:
        raise ValueError(f"unknown harness {harness!r}; known: {sorted(ADAPTERS)}") from None


__all__ = ["ADAPTERS", "Adapter", "get"]
