"""claws-bap end to end: payload in, JSON out, never a non-zero exit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claws.cli import bap as cli
from claws.testing import fixture_payloads, permission, run_cli, shell_payload


@pytest.mark.parametrize("harness", ["claude", "codex"])
def test_fixtures_run_clean(harness: str) -> None:
    for payload in fixture_payloads(harness, "PreToolUse"):
        out, _ = run_cli(["paws", "--harness", harness], json.dumps(payload))
        assert out == {}, payload


@pytest.mark.parametrize("harness", ["claude", "codex"])
def test_deny_end_to_end(harness: str) -> None:
    out, _ = run_cli(["paws", "--harness", harness], json.dumps(shell_payload(harness, "git reset --hard")))
    decision, reason = permission(out)
    assert decision == "deny"
    assert "git-reset-hard" in reason


def test_malformed_payload_fails_closed() -> None:
    out, err = run_cli(["paws", "--harness", "claude"], "this is not json")
    decision, reason = permission(out)
    assert decision == "deny"
    assert "crashed" in reason
    assert "paws" in err


def test_empty_stdin_is_quiet() -> None:
    out, _ = run_cli(["paws", "--harness", "claude"], "")
    assert out == {}


def test_unknown_bap_still_exits_zero() -> None:
    out, err = run_cli(["nope", "--harness", "claude"], "{}")
    assert out == {}
    assert "unknown bap" in err


def test_unknown_harness_still_exits_zero() -> None:
    out, err = run_cli(["paws", "--harness", "gemini"], json.dumps(shell_payload("claude", "ls")))
    assert permission(out)[0] == "deny"
    assert "unknown harness" in err


def test_broken_config_fails_closed(tmp_path: Path) -> None:
    cfg = tmp_path / "c.json"
    cfg.write_text("{nope")
    out, _ = run_cli(["paws", "--harness", "claude", "--config", str(cfg)], json.dumps(shell_payload("claude", "ls")))
    assert permission(out)[0] == "deny"


def test_log_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAWS_NO_LOG")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    cli.respond("paws", "claude", shell_payload("claude", "rm -rf /"), None)
    lines = (tmp_path / "claws" / "paws.jsonl").read_text().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["action"] == "deny" and rec["command"] == "rm -rf /"
