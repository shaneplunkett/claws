"""The normalised shapes baps work with.

Adapters turn a harness payload into an Event and a Decision back into the
harness's response. Baps only ever see these two types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .jsontypes import JsonObject

ToolClass = Literal["shell", "edit", "other"]
Action = Literal["allow", "deny", "ask", "none"]


@dataclass(frozen=True)
class Event:
    harness: str
    kind: str  # PreToolUse, PostToolUse, SessionStart, UserPromptSubmit, Stop
    tool: ToolClass | None = None
    raw_tool_name: str | None = None
    command: str | None = None
    paths: tuple[str, ...] = ()
    cwd: str | None = None
    session_id: str | None = None
    permission_mode: str | None = None  # e.g. default, acceptEdits, bypassPermissions, dontAsk
    raw: JsonObject = field(default_factory=dict, compare=False, repr=False)

    @property
    def unattended(self) -> bool:
        """True when the harness will not put a question in front of a human."""
        return self.permission_mode in ("bypassPermissions", "dontAsk")


@dataclass(frozen=True)
class Decision:
    action: Action = "none"
    reason: str | None = None
    context: str | None = None  # extra text fed back to the model

    @classmethod
    def allow(cls) -> Decision:
        return cls("allow")

    @classmethod
    def deny(cls, reason: str) -> Decision:
        return cls("deny", reason)

    @classmethod
    def ask(cls, reason: str) -> Decision:
        return cls("ask", reason)

    @classmethod
    def none(cls) -> Decision:
        return cls("none")
