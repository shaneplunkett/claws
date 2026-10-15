"""Config layering: defaults, then --config/$CLAWS_CONFIG, then .claws.json up to the git root."""

from __future__ import annotations

import json
from pathlib import Path

from claws.baps import paws
from claws.core import config
from claws.testing import permission, run_cli, shell_payload


def test_explicit_config_file(tmp_path: Path) -> None:
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"baps": {"paws": {"level": "critical"}}}))
    out, _ = run_cli(
        ["paws", "--harness", "claude", "--config", str(cfg)], json.dumps(shell_payload("claude", "git reset --hard"))
    )
    assert out == {}


def test_env_config_file(tmp_path: Path) -> None:
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"baps": {"paws": {"ask": True}}}))
    out, _ = run_cli(
        ["paws", "--harness", "claude"],
        json.dumps(shell_payload("claude", "git reset --hard")),
        env={"CLAWS_CONFIG": str(cfg)},
    )
    assert permission(out)[0] == "ask"


def test_project_config_found_from_cwd(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".claws.json").write_text(json.dumps({"baps": {"paws": {"disable": ["git-reset-hard"]}}}))
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    out, _ = run_cli(
        ["paws", "--harness", "claude"], json.dumps(shell_payload("claude", "git reset --hard", cwd=str(sub)))
    )
    assert out == {}


def test_project_config_stops_at_git_root(tmp_path: Path) -> None:
    (tmp_path / ".claws.json").write_text(json.dumps({"baps": {"paws": {"disable": ["git-reset-hard"]}}}))
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    out, _ = run_cli(
        ["paws", "--harness", "claude"], json.dumps(shell_payload("claude", "git reset --hard", cwd=str(repo)))
    )
    assert permission(out)[0] == "deny"


def test_layers_merge_lists_and_override_scalars(tmp_path: Path) -> None:
    glob = tmp_path / "g.json"
    glob.write_text(json.dumps({"baps": {"paws": {"level": "medium", "allow": ["^a$"]}}}))
    (tmp_path / ".git").mkdir()
    (tmp_path / ".claws.json").write_text(json.dumps({"baps": {"paws": {"level": "low", "allow": ["^b$"]}}}))
    opts = config.for_bap("paws", paws.BAP.options(), str(glob), str(tmp_path))
    assert opts["level"] == "low"
    assert opts["allow"] == ["^a$", "^b$"]


def test_merge_nested_objects() -> None:
    assert config.merge({"a": {"x": 1, "l": [1]}}, {"a": {"y": 2, "l": [2]}, "b": 3}) == {
        "a": {"x": 1, "y": 2, "l": [1, 2]},
        "b": 3,
    }


def test_missing_section_is_fine(tmp_path: Path) -> None:
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"baps": {"other": {"x": 1}}}))
    assert config.for_bap("paws", {"level": "high"}, str(cfg), None) == {"level": "high"}
