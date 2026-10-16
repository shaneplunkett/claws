from __future__ import annotations

import pytest

from claws import adapters
from claws.core.events import Decision, Event
from claws.core.jsontypes import JsonObject
from claws.testing import all_fixtures, fixture_payloads

CASES = all_fixtures()


@pytest.mark.parametrize(
    "harness,event,payload", CASES, ids=[f"{h}-{e}-{p.get('tool_name', '')}" for h, e, p in CASES]
)
def test_every_fixture_parses(harness: str, event: str, payload: JsonObject) -> None:
    ev = adapters.get(harness).parse(payload)
    assert ev.harness == harness
    assert ev.kind == event
    assert ev.cwd
    assert ev.session_id
    if event.endswith("ToolUse"):
        assert ev.raw_tool_name
        assert ev.tool in ("shell", "edit", "other")
    else:
        assert ev.tool is None


@pytest.mark.parametrize("harness", ["claude", "codex"])
def test_shell_commands_come_through(harness: str) -> None:
    commands = {
        adapters.get(harness).parse(p).command
        for p in fixture_payloads(harness, "PreToolUse")
        if p["tool_name"] == "Bash"
    }
    assert "echo claws-fixture" in commands


@pytest.mark.parametrize("harness", ["claude", "codex"])
def test_permission_mode_comes_through(harness: str) -> None:
    modes = {
        adapters.get(harness).parse(p).permission_mode
        for p in fixture_payloads(harness, "PreToolUse")
    }
    assert modes == {"bypassPermissions"}


def test_missing_permission_mode_is_none() -> None:
    ev = adapters.get("claude").parse(
        {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"}}
    )
    assert ev.permission_mode is None


def test_claude_edit_paths() -> None:
    paths = {
        adapters.get("claude").parse(p).paths
        for p in fixture_payloads("claude", "PreToolUse")
        if p["tool_name"] in ("Edit", "Write")
    }
    assert paths == {("/tmp/claws-fx/claude-proj/note.txt",)}


def test_codex_apply_patch_paths() -> None:
    patches = [
        p for p in fixture_payloads("codex", "PreToolUse") if p["tool_name"] == "apply_patch"
    ]
    assert patches, "fixture set lost its apply_patch sample"
    ev = adapters.get("codex").parse(patches[0])
    assert ev.tool == "edit"
    assert ev.paths == ("/tmp/claws-fx/codex-proj/note.txt",)


def test_codex_apply_patch_multiple_files() -> None:
    patch = "*** Begin Patch\n*** Add File: a.py\n+x\n*** Update File: b/c.py\n@@\n-1\n+2\n*** Delete File: d\n*** End Patch"
    ev = adapters.get("codex").parse(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "apply_patch",
            "tool_input": {"command": patch},
        }
    )
    assert ev.paths == ("a.py", "b/c.py", "d")


def test_codex_legacy_exec_command_shape() -> None:
    ev = adapters.get("codex").parse(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "exec_command",
            "tool_input": {"cmd": ["git", "reset", "--hard"]},
        }
    )
    assert ev.tool == "shell"
    assert ev.command == "git reset --hard"


def test_unknown_tool_is_other() -> None:
    ev = adapters.get("claude").parse(
        {"hook_event_name": "PreToolUse", "tool_name": "WebFetch", "tool_input": {"url": "x"}}
    )
    assert ev.tool == "other"
    assert ev.command is None


def test_unknown_harness() -> None:
    with pytest.raises(ValueError):
        adapters.get("gemini")


@pytest.mark.parametrize("harness", ["claude", "codex"])
class TestRender:
    def test_none_is_empty(self, harness: str) -> None:
        ev = Event(harness=harness, kind="PreToolUse")
        assert adapters.get(harness).render(Decision.none(), ev) == {}

    def test_deny_pre_tool_use(self, harness: str) -> None:
        ev = Event(harness=harness, kind="PreToolUse")
        out = adapters.get(harness).render(Decision.deny("nope"), ev)
        assert out == {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "nope",
            }
        }

    def test_allow_pre_tool_use(self, harness: str) -> None:
        ev = Event(harness=harness, kind="PreToolUse")
        out = adapters.get(harness).render(Decision.allow(), ev)
        assert out == {
            "hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}
        }

    def test_context_pre_tool_use(self, harness: str) -> None:
        ev = Event(harness=harness, kind="PreToolUse")
        out = adapters.get(harness).render(Decision(context="heads up"), ev)
        assert out == {
            "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "heads up"}
        }

    def test_deny_elsewhere_blocks(self, harness: str) -> None:
        ev = Event(harness=harness, kind="PostToolUse")
        out = adapters.get(harness).render(Decision.deny("bad"), ev)
        assert out["decision"] == "block"
        assert out["reason"] == "bad"
        assert "hookSpecificOutput" not in out

    def test_context_only(self, harness: str) -> None:
        ev = Event(harness=harness, kind="SessionStart")
        out = adapters.get(harness).render(Decision(context="hello"), ev)
        assert out == {
            "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "hello"}
        }
