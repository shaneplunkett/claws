"""Stop and PostToolUse responses, end to end through claws-bap with a test bap.

The expected shapes come from each harness: Claude Code's hooks docs (checked 2026-10-16)
and Codex's codex-rs/hooks source at rust-v0.162.1. See the adapters' render docstrings.
"""

from __future__ import annotations

import io
import json
from collections.abc import Callable

import pytest
from _pytest.mark import ParameterSet

from claws.adapters.base import BLOCK_REASON
from claws.cli import bap as cli
from claws.core import registry
from claws.core.events import Decision, Event
from claws.core.jsontypes import JsonObject, as_object, loads
from claws.testing import fixture_payloads

HARNESSES = ("claude", "codex")

# harness, payload, decision -> response. A None decision is a fail-closed bap that crashes.
Respond = Callable[[str, JsonObject, Decision | None], JsonObject]


@pytest.fixture
def respond(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> Respond:
    """Run claws-bap's main, the harness entrypoint, with a one-off bap returning `decision`."""

    def go(harness: str, payload: JsonObject, decision: Decision | None) -> JsonObject:
        def run(event: Event, options: JsonObject) -> Decision:
            if decision is None:
                raise RuntimeError("boom")
            return decision

        kind = str(payload["hook_event_name"])
        test_bap = registry.Bap(name="test-bap", event=kind, run=run, fail_closed=True)
        monkeypatch.setattr(registry, "discover", lambda: {"test-bap": test_bap})
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        monkeypatch.setenv("CLAWS_NO_LOG", "1")
        monkeypatch.delenv("CLAWS_CONFIG", raising=False)
        capsys.readouterr()
        assert cli.main(["test-bap", "--harness", harness]) == 0
        return as_object(loads(capsys.readouterr().out), "stdout")

    return go


def captured(event: str, harnesses: tuple[str, ...] = HARNESSES) -> list[ParameterSet]:
    """Every captured payload for the event, on each harness."""
    return [
        pytest.param(harness, payload, id=f"{harness}-{i}")
        for harness in harnesses
        for i, payload in enumerate(fixture_payloads(harness, event))
    ]


def block(reason: str) -> JsonObject:
    return {"decision": "block", "reason": reason}


def context(kind: str, text: str) -> JsonObject:
    return {"hookSpecificOutput": {"hookEventName": kind, "additionalContext": text}}


@pytest.mark.parametrize(("harness", "payload"), captured("Stop") + captured("PostToolUse"))
class TestBothEvents:
    def test_pass_is_empty(self, respond: Respond, harness: str, payload: JsonObject) -> None:
        assert respond(harness, payload, Decision.none()) == {}
        assert respond(harness, payload, Decision.allow()) == {}

    def test_deny_blocks_with_the_reason(
        self, respond: Respond, harness: str, payload: JsonObject
    ) -> None:
        # Stop: the reason becomes the prompt to keep going. PostToolUse: feedback on the result.
        assert respond(harness, payload, Decision.deny("tests are failing")) == block(
            "tests are failing"
        )

    def test_blank_reason_still_blocks(
        self, respond: Respond, harness: str, payload: JsonObject
    ) -> None:
        # Codex reads a block with a blank reason as invalid output and lets it pass.
        assert respond(harness, payload, Decision.deny("  ")) == block(BLOCK_REASON)

    def test_crash_in_a_fail_closed_bap_blocks(
        self, respond: Respond, harness: str, payload: JsonObject
    ) -> None:
        out = respond(harness, payload, None)
        assert out.keys() == {"decision", "reason"}
        assert out["decision"] == "block"
        assert "test-bap crashed (boom)" in str(out["reason"])


@pytest.mark.parametrize(("harness", "payload"), captured("PostToolUse"))
def test_post_tool_use_context(respond: Respond, harness: str, payload: JsonObject) -> None:
    assert respond(harness, payload, Decision(context="lint is clean")) == context(
        "PostToolUse", "lint is clean"
    )
    deny = Decision("deny", "lint failed", "see ruff output")
    assert respond(harness, payload, deny) == {
        **block("lint failed"),
        **context("PostToolUse", "see ruff output"),
    }


@pytest.mark.parametrize(("harness", "payload"), captured("Stop", ("claude",)))
def test_claude_stop_context(respond: Respond, harness: str, payload: JsonObject) -> None:
    # Claude shows Stop context as hook feedback and keeps going.
    assert respond(harness, payload, Decision(context="remember the changelog")) == context(
        "Stop", "remember the changelog"
    )


@pytest.mark.parametrize(("harness", "payload"), captured("Stop", ("codex",)))
def test_codex_stop_drops_context(respond: Respond, harness: str, payload: JsonObject) -> None:
    # Codex's Stop output has no hookSpecificOutput and rejects unknown fields, so context
    # would invalidate the response. A block would force another turn, which context doesn't
    # mean, so the context is dropped and a deny keeps its block.
    assert respond(harness, payload, Decision(context="remember the changelog")) == {}
    deny = Decision("deny", "tests are failing", "remember the changelog")
    assert respond(harness, payload, deny) == block("tests are failing")
