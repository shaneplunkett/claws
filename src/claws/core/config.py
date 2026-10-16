"""Bap configuration.

Layers, lowest to highest:
  1. the bap's defaults
  2. --config FILE or $CLAWS_CONFIG (what home-manager and lib.project pass)

The file is {"baps": {"<bap>": {...options}}}. Scalars override, lists
concatenate. Each scope passes its own file, and scopes never merge (ADR 0008).
"""

from __future__ import annotations

import os
from pathlib import Path

from .jsontypes import JsonObject, as_object, loads


def load_file(path: Path) -> JsonObject:
    return as_object(loads(path.read_text()), f"{path}: top level")


def merge(base: JsonObject, over: JsonObject) -> JsonObject:
    out = dict(base)
    for key, value in over.items():
        current = out.get(key)
        if isinstance(value, list) and isinstance(current, list):
            out[key] = current + value
        elif isinstance(value, dict) and isinstance(current, dict):
            out[key] = merge(current, value)
        else:
            out[key] = value
    return out


def layers(explicit: str | None) -> list[Path]:
    explicit = explicit or os.environ.get("CLAWS_CONFIG")
    return [Path(explicit)] if explicit else []


def for_bap(bap: str, defaults: JsonObject, explicit: str | None) -> JsonObject:
    result = dict(defaults)
    for path in layers(explicit):
        baps = as_object(load_file(path).get("baps", {}), f"{path}: baps")
        section = as_object(baps.get(bap, {}), f"{path}: baps.{bap}")
        result = merge(result, section)
    return result
