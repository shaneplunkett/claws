"""Helpers for bap tests and cross-cutting tests. Import from here, not from a conftest."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .core.events import Event
from .core.jsontypes import JsonObject, as_object, as_str, loads

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SRC = Path(__file__).resolve().parents[1]


def fixture_payloads(harness: str, event: str) -> list[JsonObject]:
    path = FIXTURES / harness / f"{event}.jsonl"
    return [as_object(loads(line), path.name) for line in path.read_text().splitlines() if line.strip()]


def all_fixtures() -> list[tuple[str, str, JsonObject]]:
    out: list[tuple[str, str, JsonObject]] = []
    for harness_dir in sorted(FIXTURES.iterdir()):
        for file in sorted(harness_dir.glob("*.jsonl")):
            for payload in fixture_payloads(harness_dir.name, file.stem):
                out.append((harness_dir.name, file.stem, payload))
    return out


def shell_payload(harness: str, command: str, cwd: str | None = None) -> JsonObject:
    """A PreToolUse shell payload in the shape both harnesses send."""
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": cwd or "/tmp/nowhere",
        "session_id": "test",
    }


def shell_event(command: str, harness: str = "claude") -> Event:
    return Event(harness=harness, kind="PreToolUse", tool="shell", raw_tool_name="Bash", command=command)


def edit_event(*paths: str, harness: str = "claude") -> Event:
    return Event(harness=harness, kind="PreToolUse", tool="edit", raw_tool_name="Edit", paths=paths)


def permission(out: JsonObject) -> tuple[str, str]:
    """(permissionDecision, permissionDecisionReason) from a PreToolUse response."""
    specific = as_object(out["hookSpecificOutput"], "hookSpecificOutput")
    return as_str(specific["permissionDecision"], "decision"), as_str(
        specific.get("permissionDecisionReason", ""), "reason"
    )


def run_cli(args: list[str], stdin: str, env: dict[str, str] | None = None) -> tuple[JsonObject, str]:
    """Run claws-bap the way a harness does: a fresh isolated interpreter, stdin in, JSON out.
    -I drops PYTHONPATH, so point at the source tree explicitly via a -c shim."""
    code = f"import sys; sys.path.insert(0, {str(SRC)!r}); from claws.cli.bap import main; sys.exit(main(sys.argv[1:]))"
    proc = subprocess.run(
        [sys.executable, "-I", "-c", code, *args],
        input=stdin,
        capture_output=True,
        text=True,
        env={**os.environ, "CLAWS_NO_LOG": "1", **(env or {})},
    )
    assert proc.returncode == 0, proc.stderr
    return as_object(loads(proc.stdout), "stdout"), proc.stderr
