from __future__ import annotations

import re
from typing import ClassVar

from ..core.events import ToolClass
from ..core.jsontypes import Json
from .base import Adapter, command_string, edit_paths

# apply_patch headers: "*** Update File: path", "*** Add File: path", "*** Delete File: path",
# "*** Move to: path"
_PATCH_PATH = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$|^\*\*\* Move to: (.+)$", re.MULTILINE)


class CodexAdapter(Adapter):
    """Codex 0.162+ sends Claude-shaped payloads for shell (tool_name Bash,
    tool_input.command). Older builds used exec_command with tool_input.cmd,
    kept here so a stale Codex still gets guarded. Edits arrive as apply_patch
    with the whole patch in tool_input.command."""

    name = "codex"
    shell_tools = frozenset({"Bash", "exec_command", "functions.exec_command", "shell", "local_shell"})
    edit_tools = frozenset({"apply_patch", "Edit", "Write", "MultiEdit"})
    matchers: ClassVar[dict[str, str]] = {
        "shell": "Bash|exec_command|functions.exec_command|shell|local_shell",
        "edit": "apply_patch|Edit|Write|MultiEdit",
    }

    def parse_tool(self, raw_tool: str | None, tool_input: Json) -> tuple[ToolClass | None, str | None, list[str]]:
        if raw_tool == "apply_patch":
            patch = command_string(tool_input) or ""
            paths = [a or b for a, b in _PATCH_PATH.findall(patch)]
            return "edit", None, paths or edit_paths(tool_input)
        return super().parse_tool(raw_tool, tool_input)
