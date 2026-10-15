from __future__ import annotations

from typing import ClassVar

from .base import Adapter


class ClaudeAdapter(Adapter):
    name = "claude"
    shell_tools = frozenset({"Bash"})
    edit_tools = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})
    matchers: ClassVar[dict[str, str]] = {
        "shell": "Bash",
        "edit": "Edit|Write|MultiEdit|NotebookEdit",
    }
