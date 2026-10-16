from __future__ import annotations

from claws.cli import manifest


def test_manifest_lists_dangerous_commands() -> None:
    m = manifest.manifest()
    assert m["dangerous-commands"] == {
        "event": "PreToolUse",
        "tools": ["shell", "edit"],
        "timeout": 10,
    }


def test_render_claude() -> None:
    out = manifest.render(
        "claude", ["dangerous-commands"], "/nix/store/x/bin/claws-bap", "/nix/store/y/claws.json"
    )
    assert list(out) == ["PreToolUse"]
    entry = out["PreToolUse"][0]
    assert entry["matcher"] == "Bash|Edit|Write|MultiEdit|NotebookEdit"
    assert entry["hooks"] == [
        {
            "type": "command",
            "command": "/nix/store/x/bin/claws-bap dangerous-commands --harness claude --config /nix/store/y/claws.json",
            "timeout": 10,
        }
    ]


def test_render_codex_matchers_include_apply_patch() -> None:
    out = manifest.render("codex", ["dangerous-commands"], "claws-bap")
    assert "apply_patch" in out["PreToolUse"][0]["matcher"]
    assert (
        out["PreToolUse"][0]["hooks"][0]["command"]
        == "claws-bap dangerous-commands --harness codex"
    )
