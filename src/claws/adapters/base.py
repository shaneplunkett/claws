from __future__ import annotations

import shlex
from typing import ClassVar

from ..core.events import Decision, Event, ToolClass
from ..core.jsontypes import HookResponse, HookSpecificOutput, Json, JsonObject


class Adapter:
    """Base adapter. Subclasses set the tool-name tables and override parse_tool."""

    name = "base"
    shell_tools: frozenset[str] = frozenset()
    edit_tools: frozenset[str] = frozenset()

    # Regex matchers each harness expects in its hook config, by tool class.
    matchers: ClassVar[dict[str, str]] = {}

    def parse(self, payload: JsonObject) -> Event:
        kind = str(payload.get("hook_event_name") or "")
        raw_tool_value = payload.get("tool_name")
        raw_tool = raw_tool_value if isinstance(raw_tool_value, str) else None
        tool, command, paths = self.parse_tool(raw_tool, payload.get("tool_input"))
        cwd = payload.get("cwd")
        session_id = payload.get("session_id")
        return Event(
            harness=self.name,
            kind=kind,
            tool=tool,
            raw_tool_name=raw_tool,
            command=command,
            paths=tuple(paths),
            cwd=cwd if isinstance(cwd, str) else None,
            session_id=session_id if isinstance(session_id, str) else None,
            raw=payload,
        )

    def parse_tool(self, raw_tool: str | None, tool_input: Json) -> tuple[ToolClass | None, str | None, list[str]]:
        if raw_tool is None:
            return None, None, []
        if raw_tool in self.shell_tools:
            return "shell", command_string(tool_input), []
        if raw_tool in self.edit_tools:
            return "edit", None, edit_paths(tool_input)
        return "other", None, []

    def render(self, decision: Decision, event: Event) -> HookResponse:
        """Both harnesses speak the same response dialect. Override if one drifts."""
        if decision.action == "none" and not decision.context:
            return {}
        out: HookResponse = {}
        specific: HookSpecificOutput = {"hookEventName": event.kind}
        if event.kind == "PreToolUse" and decision.action in ("allow", "deny", "ask"):
            specific["permissionDecision"] = decision.action
            if decision.reason:
                specific["permissionDecisionReason"] = decision.reason
        elif decision.action == "deny":
            # Outside PreToolUse the only hard stop is the top-level decision.
            out["decision"] = "block"
            if decision.reason:
                out["reason"] = decision.reason
        if decision.context:
            specific["additionalContext"] = decision.context
        if len(specific) > 1:
            out["hookSpecificOutput"] = specific
        return out


def command_string(tool_input: Json) -> str | None:
    if isinstance(tool_input, str):
        return tool_input
    if not isinstance(tool_input, dict):
        return None
    for key in ("command", "cmd"):
        value = tool_input.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            words = [v for v in value if isinstance(v, str)]
            if len(words) == len(value):
                return shlex.join(words)
    return None


def edit_paths(tool_input: Json) -> list[str]:
    if not isinstance(tool_input, dict):
        return []
    paths = []
    for key in ("file_path", "notebook_path", "path"):
        value = tool_input.get(key)
        if isinstance(value, str):
            paths.append(value)
    return paths
