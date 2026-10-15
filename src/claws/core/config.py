"""Bap configuration.

Layers, lowest to highest:
  1. the bap's defaults
  2. --config FILE or $CLAWS_CONFIG (what the home-manager module passes)
  3. .claws.json in the event's cwd, walking up to the git root (project level)

Each file is {"baps": {"<bap>": {...options}}}. Scalars override, lists
concatenate, so a project can add rules on top of global ones.
"""

from __future__ import annotations

import os
from pathlib import Path

from .jsontypes import JsonObject, as_object, loads

PROJECT_FILE = ".claws.json"


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


def find_project_file(start: str | None) -> Path | None:
    if not start:
        return None
    here = Path(start).resolve()
    for directory in (here, *here.parents):
        candidate = directory / PROJECT_FILE
        if candidate.is_file():
            return candidate
        if (directory / ".git").exists():
            break
    return None


def layers(explicit: str | None, cwd: str | None) -> list[Path]:
    found: list[Path] = []
    explicit = explicit or os.environ.get("CLAWS_CONFIG")
    if explicit:
        found.append(Path(explicit))
    project = find_project_file(cwd)
    if project and project not in found:
        found.append(project)
    return found


def for_bap(bap: str, defaults: JsonObject, explicit: str | None, cwd: str | None) -> JsonObject:
    result = dict(defaults)
    for path in layers(explicit, cwd):
        baps = as_object(load_file(path).get("baps", {}), f"{path}: baps")
        section = as_object(baps.get(bap, {}), f"{path}: baps.{bap}")
        result = merge(result, section)
    return result
