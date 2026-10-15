"""Every bap package is discovered and satisfies the contract."""

from __future__ import annotations

import pytest

from claws.core import registry


def test_discovers_dangerous_commands() -> None:
    baps = registry.discover()
    assert "dangerous-commands" in baps
    assert baps["dangerous-commands"].event == "PreToolUse"
    assert baps["dangerous-commands"].fail_closed is True


def test_names_sorted() -> None:
    assert registry.names() == sorted(registry.names())


def test_every_bap_is_well_formed() -> None:
    for name, bap in registry.discover().items():
        assert bap.name == name
        assert bap.event in {"PreToolUse", "PostToolUse", "SessionStart", "UserPromptSubmit", "Stop"}
        assert set(bap.tools) <= {"shell", "edit"}
        assert bap.timeout > 0
        assert callable(bap.run)


def test_unknown_bap() -> None:
    with pytest.raises(ValueError, match="unknown bap"):
        registry.get("nope")
