from __future__ import annotations

import json
from pathlib import Path

import pytest

from claws.cli import install


def test_install_writes_all_three_files(tmp_path: Path) -> None:
    rc = install.main(
        [
            "--dir",
            str(tmp_path),
            "--baps",
            "dangerous-commands",
            "--bin",
            "/nix/store/x/bin/claws-bap",
            "--set",
            "dangerous-commands.level=medium",
            "--set",
            "dangerous-commands.ask=true",
        ]
    )
    assert rc == 0
    m = json.loads((tmp_path / ".claws.json").read_text())
    assert m == {"baps": {"dangerous-commands": {"level": "medium", "ask": True}}}
    for rel in (".claude/settings.local.json", ".codex/hooks.json"):
        data = json.loads((tmp_path / rel).read_text())
        cmd = data["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        assert cmd.startswith("/nix/store/x/bin/claws-bap dangerous-commands --harness ")
        assert cmd.endswith(f"--config {tmp_path / '.claws.json'}")


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
    install.main(
        [
            "--dir",
            str(tmp_path),
            "--harness",
            "claude",
            "--baps",
            "dangerous-commands",
            "--bin",
            "/nix/store/new/bin/claws-bap",
        ]
    )
    data = json.loads(settings.read_text())
    assert data["permissions"] == {"allow": ["Bash(ls)"]}
    cmds = [h["command"] for e in data["hooks"]["PreToolUse"] for h in e["hooks"]]
    assert cmds[0] == "/their/thing"
    assert len(cmds) == 2 and cmds[1].startswith("/nix/store/new/")
    assert data["hooks"]["Stop"][0]["hooks"][0]["command"] == "/their/stop"


def test_install_reuses_manifest_baps(tmp_path: Path) -> None:
    (tmp_path / ".claws.json").write_text(
        json.dumps({"baps": {"dangerous-commands": {"level": "low"}}})
    )
    install.main(["--dir", str(tmp_path), "--harness", "codex", "--bin", "x"])
    m = json.loads((tmp_path / ".claws.json").read_text())
    assert m["baps"]["dangerous-commands"]["level"] == "low"
    assert (tmp_path / ".codex" / "hooks.json").exists()


def test_install_rejects_unknown_bap(tmp_path: Path) -> None:

    with pytest.raises(ValueError):
        install.main(["--dir", str(tmp_path), "--baps", "nope", "--bin", "x"])


def test_install_from_declarative_config(tmp_path: Path) -> None:
    cfg = tmp_path / "store" / "claws.json"
    cfg.parent.mkdir()
    cfg.write_text(
        json.dumps({"harnesses": ["codex"], "baps": {"dangerous-commands": {"level": "low"}}})
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    assert (
        install.main(
            ["--dir", str(repo), "--from", str(cfg), "--bin", "/nix/store/x/bin/claws-bap"]
        )
        == 0
    )
    assert not (repo / ".claws.json").exists(), "declarative mode must not write a manifest"
    assert not (repo / ".claude").exists(), "harnesses came from the file"
    data = json.loads((repo / ".codex" / "hooks.json").read_text())
    cmd = data["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert cmd == f"/nix/store/x/bin/claws-bap dangerous-commands --harness codex --config {cfg}"


def test_from_rejects_baps_and_set(tmp_path: Path) -> None:
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"baps": {"dangerous-commands": {}}}))
    with pytest.raises(SystemExit):
        install.main(
            [
                "--dir",
                str(tmp_path),
                "--from",
                str(cfg),
                "--baps",
                "dangerous-commands",
                "--bin",
                "x",
            ]
        )


def test_install_is_idempotent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    install.main(["--dir", str(tmp_path), "--baps", "dangerous-commands", "--bin", "x"])
    before = {p: p.read_text() for p in tmp_path.rglob("*.json")}
    capsys.readouterr()
    install.main(["--dir", str(tmp_path), "--baps", "dangerous-commands", "--bin", "x", "--quiet"])
    assert capsys.readouterr().out == ""
    assert {p: p.read_text() for p in tmp_path.rglob("*.json")} == before


def test_generated_files_are_git_excluded(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    install.main(["--dir", str(tmp_path), "--baps", "dangerous-commands", "--bin", "x"])
    install.main(["--dir", str(tmp_path), "--baps", "dangerous-commands", "--bin", "x"])
    lines = (tmp_path / ".git" / "info" / "exclude").read_text().splitlines()
    assert lines == [".claude/settings.local.json", ".codex/hooks.json"]


def test_git_exclude_appends_to_file_without_trailing_newline(tmp_path: Path) -> None:
    (tmp_path / ".git" / "info").mkdir(parents=True)
    (tmp_path / ".git" / "info" / "exclude").write_text("*.swp")
    install.main(
        ["--dir", str(tmp_path), "--harness", "codex", "--baps", "dangerous-commands", "--bin", "x"]
    )
    assert (tmp_path / ".git" / "info" / "exclude").read_text() == "*.swp\n.codex/hooks.json\n"


def test_no_git_dir_is_fine(tmp_path: Path) -> None:
    install.main(["--dir", str(tmp_path), "--baps", "dangerous-commands", "--bin", "x"])
    assert not (tmp_path / ".git").exists()
