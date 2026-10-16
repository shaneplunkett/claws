"""Config layering: defaults, then --config/$CLAWS_CONFIG."""

from __future__ import annotations

import json
from pathlib import Path

from claws.baps import dangerous_commands as paws
from claws.core import config
from claws.testing import permission, run_cli, shell_payload


def test_explicit_config_file(tmp_path: Path) -> None:
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"baps": {"dangerous-commands": {"level": "critical"}}}))
    out, _ = run_cli(
        ["dangerous-commands", "--harness", "claude", "--config", str(cfg)],
        json.dumps(shell_payload("claude", "git reset --hard")),
    )
    assert out == {}


def test_env_config_file(tmp_path: Path) -> None:
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"baps": {"dangerous-commands": {"level": "critical"}}}))
    out, _ = run_cli(
        ["dangerous-commands", "--harness", "claude"],
        json.dumps(shell_payload("claude", "git reset --hard")),
        env={"CLAWS_CONFIG": str(cfg)},
    )
    assert out == {}


def test_retired_ask_options_still_deny_by_rule(tmp_path: Path) -> None:
    cfg = tmp_path / "c.json"
    retired = {"ask": True, "deny": [], "unattended": "allow"}
    cfg.write_text(json.dumps({"baps": {"dangerous-commands": retired}}))
    out, _ = run_cli(
        ["dangerous-commands", "--harness", "claude", "--config", str(cfg)],
        json.dumps(shell_payload("claude", "git reset --hard")),
    )
    decision, reason = permission(out)
    assert decision == "deny"
    assert "git-reset-hard" in reason


def test_stray_claws_json_is_ignored(tmp_path: Path) -> None:
    # ADR 0003 retired the per-repo manifest; a leftover one must not loosen anything.
    (tmp_path / ".git").mkdir()
    (tmp_path / ".claws.json").write_text(
        json.dumps({"baps": {"dangerous-commands": {"disable": ["git-reset-hard"]}}})
    )
    out, _ = run_cli(
        ["dangerous-commands", "--harness", "claude"],
        json.dumps(shell_payload("claude", "git reset --hard", cwd=str(tmp_path))),
    )
    assert permission(out)[0] == "deny"


def test_config_file_merges_over_defaults(tmp_path: Path) -> None:
    cfg = tmp_path / "c.json"
    cfg.write_text(
        json.dumps({"baps": {"dangerous-commands": {"level": "medium", "allow": ["^a$"]}}})
    )
    opts = config.for_bap("dangerous-commands", {**paws.BAP.options(), "allow": ["^d$"]}, str(cfg))
    assert opts["level"] == "medium"
    assert opts["allow"] == ["^d$", "^a$"]


def test_merge_nested_objects() -> None:
    assert config.merge({"a": {"x": 1, "l": [1]}}, {"a": {"y": 2, "l": [2]}, "b": 3}) == {
        "a": {"x": 1, "y": 2, "l": [1, 2]},
        "b": 3,
    }


def test_missing_section_is_fine(tmp_path: Path) -> None:
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"baps": {"other": {"x": 1}}}))
    assert config.for_bap("dangerous-commands", {"level": "high"}, str(cfg)) == {"level": "high"}
