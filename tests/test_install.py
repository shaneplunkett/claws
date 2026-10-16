from __future__ import annotations

import json
from pathlib import Path

import pytest

from claws.cli import install
from claws.core.jsontypes import JsonObject


def bap_set(tmp_path: Path, declared: JsonObject | None = None) -> Path:
    """A stand-in for the claws.json lib.project writes to the store."""
    cfg = tmp_path / "store" / "claws.json"
    cfg.parent.mkdir(exist_ok=True)
    cfg.write_text(json.dumps(declared or {"baps": {"dangerous-commands": {"level": "high"}}}))
    return cfg


def run(repo: Path, cfg: Path, binary: str, *extra: str) -> int:
    return install.main(["--dir", str(repo), "--from", str(cfg), "--bin", binary, *extra])


def test_install_writes_both_harness_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = bap_set(tmp_path)
    assert run(repo, cfg, "/nix/store/x/bin/claws-bap") == 0
    for harness, rel in (
        ("claude", ".claude/settings.local.json"),
        ("codex", ".codex/hooks.json"),
    ):
        data = json.loads((repo / rel).read_text())
        cmd = data["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        expected = (
            f"/nix/store/x/bin/claws-bap dangerous-commands --harness {harness} --config {cfg}"
        )
        assert cmd == expected
    assert not (repo / ".claws.json").exists(), "no manifest in the repo"


def test_harnesses_come_from_the_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = bap_set(
        tmp_path, {"harnesses": ["codex"], "baps": {"dangerous-commands": {"level": "low"}}}
    )
    run(repo, cfg, "x")
    assert not (repo / ".claude").exists()
    assert (repo / ".codex" / "hooks.json").exists()


def test_install_keeps_foreign_entries_and_replaces_ours(tmp_path: Path) -> None:
    settings = tmp_path / ".claude" / "settings.local.json"
    settings.parent.mkdir()
    settings.write_text(
        json.dumps(
            {
                "permissions": {"allow": ["Bash(ls)"]},
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [{"type": "command", "command": "/their/thing"}],
                        },
                        {
                            "matcher": "Bash",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "/nix/store/old/bin/claws-bap dangerous-commands --harness claude",
                                }
                            ],
                        },
                        {
                            "matcher": "Bash",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "/nix/store/older/bin/claws-hook paws --harness claude",
                                }
                            ],
                        },
                    ],
                    "Stop": [{"hooks": [{"type": "command", "command": "/their/stop"}]}],
                },
            }
        )
    )
    cfg = bap_set(tmp_path, {"harnesses": ["claude"], "baps": {"dangerous-commands": {}}})
    run(tmp_path, cfg, "/nix/store/new/bin/claws-bap")
    data = json.loads(settings.read_text())
    assert data["permissions"] == {"allow": ["Bash(ls)"]}
    cmds = [h["command"] for e in data["hooks"]["PreToolUse"] for h in e["hooks"]]
    assert cmds[0] == "/their/thing"
    assert len(cmds) == 2 and cmds[1].startswith("/nix/store/new/")
    assert data["hooks"]["Stop"][0]["hooks"][0]["command"] == "/their/stop"


def test_install_rejects_unknown_bap(tmp_path: Path) -> None:
    cfg = bap_set(tmp_path, {"baps": {"nope": {}}})
    with pytest.raises(ValueError):
        run(tmp_path, cfg, "x")


def test_from_is_required(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        install.main(["--dir", str(tmp_path), "--bin", "x"])
    assert exc.value.code == 2
    assert "--from" in capsys.readouterr().err


@pytest.mark.parametrize("flag", [["--baps", "dangerous-commands"], ["--set", "a.b=c"]])
def test_ad_hoc_flags_are_gone(tmp_path: Path, flag: list[str]) -> None:
    cfg = bap_set(tmp_path)
    with pytest.raises(SystemExit) as exc:
        install.main(["--dir", str(tmp_path), "--from", str(cfg), "--bin", "x", *flag])
    assert exc.value.code == 2


def test_install_is_idempotent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = bap_set(tmp_path)
    run(repo, cfg, "x")
    before = {p: p.read_text() for p in repo.rglob("*.json")}
    capsys.readouterr()
    run(repo, cfg, "x", "--quiet")
    assert capsys.readouterr().out == ""
    assert {p: p.read_text() for p in repo.rglob("*.json")} == before


def test_generated_files_are_git_excluded(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    cfg = bap_set(tmp_path)
    run(tmp_path, cfg, "x")
    run(tmp_path, cfg, "x")
    lines = (tmp_path / ".git" / "info" / "exclude").read_text().splitlines()
    assert lines == [".claude/settings.local.json", ".codex/hooks.json"]


def test_git_exclude_appends_to_file_without_trailing_newline(tmp_path: Path) -> None:
    (tmp_path / ".git" / "info").mkdir(parents=True)
    (tmp_path / ".git" / "info" / "exclude").write_text("*.swp")
    cfg = bap_set(tmp_path, {"harnesses": ["codex"], "baps": {"dangerous-commands": {}}})
    run(tmp_path, cfg, "x")
    assert (tmp_path / ".git" / "info" / "exclude").read_text() == "*.swp\n.codex/hooks.json\n"


def test_no_git_dir_is_fine(tmp_path: Path) -> None:
    cfg = bap_set(tmp_path)
    run(tmp_path, cfg, "x")
    assert not (tmp_path / ".git").exists()
