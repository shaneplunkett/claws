"""Types for the JSON that crosses the harness boundary.

Payloads, config files and responses are JSON. These aliases keep that honest
without reaching for Any: a value is one of the JSON scalars, a list of
values, or an object of values.
"""

from __future__ import annotations

import json
from typing import TypedDict

Json = dict[str, "Json"] | list["Json"] | str | int | float | bool | None
JsonObject = dict[str, Json]


def loads(text: str) -> Json:
    value: Json = json.loads(text)
    return value


def as_object(value: Json, what: str) -> JsonObject:
    if not isinstance(value, dict):
        raise ValueError(f"{what} must be a JSON object")
    return value


def as_str(value: Json, what: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{what} must be a string")
    return value


def as_str_list(value: Json, what: str) -> list[str]:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"{what} must be a list of strings")
    return [v for v in value if isinstance(v, str)]


class HookCommand(TypedDict):
    type: str
    command: str
    timeout: int


class HookEntry(TypedDict, total=False):
    matcher: str
    hooks: list[HookCommand]


HookBlock = dict[str, list[HookEntry]]


class HookSpecificOutput(TypedDict, total=False):
    hookEventName: str
    permissionDecision: str
    permissionDecisionReason: str
    additionalContext: str


class HookResponse(TypedDict, total=False):
    decision: str
    reason: str
    hookSpecificOutput: HookSpecificOutput
