"""claws-bap <bap> --harness <claude|codex> [--config FILE]

Reads one harness payload from stdin, runs the bap, prints the response.
Always exits 0; a bap speaks through its JSON, never its exit code.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from pathlib import Path

from .. import adapters
from ..core import config, registry
from ..core.events import Decision, Event
from ..core.jsontypes import HookResponse, Json, JsonObject, as_object, loads


def log(bap: str, record: JsonObject) -> None:
    if os.environ.get("CLAWS_NO_LOG"):
        return
    try:
        base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "claws"
        base.mkdir(parents=True, exist_ok=True)
        with (base / f"{bap}.jsonl").open("a") as fh:
            fh.write(json.dumps({"ts": time.time(), **record}) + "\n")
    except OSError:
        pass


def respond(
    bap: str, harness: str, payload: JsonObject, explicit_config: str | None
) -> HookResponse:
    spec = registry.get(bap)
    adapter = adapters.get(harness)
    event = adapter.parse(payload)
    options = config.for_bap(bap, spec.options(), explicit_config, event.cwd)
    decision = spec.run(event, options)
    if decision.action in ("deny", "ask"):
        log(
            bap,
            {
                "harness": harness,
                "action": decision.action,
                "reason": decision.reason,
                "command": event.command,
                "paths": list(event.paths),
                "cwd": event.cwd,
                "session": event.session_id,
            },
        )
    return adapter.render(decision, event)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="claws-bap")
    parser.add_argument("bap")
    parser.add_argument("--harness", required=True)
    parser.add_argument("--config", default=None)
    args = parser.parse_args(argv)

    raw = sys.stdin.read()
    payload: Json = None
    out: HookResponse
    try:
        payload = loads(raw) if raw.strip() else {}
        out = respond(args.bap, args.harness, as_object(payload, "payload"), args.config)
    except Exception as exc:
        spec = None
        with contextlib.suppress(Exception):
            spec = registry.get(args.bap)
        print(f"claws-bap {args.bap}: {exc}", file=sys.stderr)
        log(args.bap, {"harness": args.harness, "action": "error", "error": str(exc)})
        if spec is not None and spec.fail_closed:
            kind = payload.get("hook_event_name") if isinstance(payload, dict) else None
            event = Event(
                harness=args.harness, kind=kind if isinstance(kind, str) else "PreToolUse"
            )
            # Both harnesses speak the base dialect, so an unknown harness still gets a deny.
            adapter = adapters.ADAPTERS.get(args.harness, adapters.Adapter())
            out = adapter.render(
                Decision.deny(f"🐾 {args.bap} crashed ({exc}); blocking to be safe"), event
            )
        else:
            out = {}
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
