from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def quiet_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAWS_NO_LOG", "1")
    monkeypatch.delenv("CLAWS_CONFIG", raising=False)
