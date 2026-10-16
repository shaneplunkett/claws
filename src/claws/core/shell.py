"""Split a shell command line into the simple commands it would run.

Regexes over a raw command string cannot tell `rm -rf /` from
`git commit -m "rm -rf /"`. This module does the minimum shell parsing needed
to make that distinction without becoming a shell:

- splits on `;`, `&&`, `||`, `|`, `&` and newlines outside quotes
- pulls `$(...)` and backtick substitutions out as commands of their own
- drops heredoc bodies and `#` comments
- unquotes tokens, so `rm -rf "~/"` reads as `rm -rf ~/`
- recurses into carriers that run their argument as a command: ssh, bash -c,
  nix develop -c, xargs, eval and friends

Each result is a Command with `view` (the unquoted tokens joined by spaces)
and `pipeline` (every view in the same pipeline joined with " | "). Rules
anchored at the start of `view` only see real command words, with the usual
prefixes (sudo, env, timeout, ...) allowed in front.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

# Prefix words a rule anchored at the command word may skip over.
PREFIX = (
    r"(?:sudo(?:\s+-\S+(?:\s+\S+)?)*|doas|nohup|nice(?:\s+-n\s*\d+)?|timeout(?:\s+-\S+)*\s+\S+"
    r"|time|command|exec|builtin|env(?:\s+-\S+)*|[A-Za-z_][A-Za-z0-9_]*=\S*)"
)
PREFIXES = re.compile(r"^(?:" + PREFIX + r"\s+)*")
# The command word may be spelled as a path: /bin/rm, /run/current-system/sw/bin/systemctl.
COMMAND_PATH = r"(?:\S*/)?"

_HEREDOC = re.compile(
    r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1([^\n]*)\n(.*?)(?:^|\n)\s*\2\s*(?=\n|$)",
    re.DOTALL | re.MULTILINE,
)
_SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh", "fish"})


@dataclass(frozen=True)
class Command:
    view: str
    pipeline: str
    raw: str


def strip_heredocs(text: str) -> str:
    """Drop heredocs entirely, keeping the rest of the opener line, where redirects live."""
    return _HEREDOC.sub(lambda m: m.group(3), text)


def _split(text: str) -> tuple[list[list[str]], list[str]]:
    """Split into pipelines of segments, plus any command substitutions found.

    Returns ([[seg, seg], [seg]], [substitution, ...]).
    """
    pipelines: list[list[str]] = [[]]
    subs: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    i = 0
    n = len(text)

    def flush(new_pipeline: bool) -> None:
        seg = "".join(buf).strip()
        buf.clear()
        if seg:
            pipelines[-1].append(seg)
        if new_pipeline and pipelines[-1]:
            pipelines.append([])

    while i < n:
        c = text[i]
        if quote:
            buf.append(c)
            if c == "\\" and quote == '"' and i + 1 < n:
                buf.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            buf.append(c + text[i + 1])
            i += 2
            continue
        if c in "'\"":
            quote = c
            buf.append(c)
            i += 1
            continue
        if c == "#" and (i == 0 or text[i - 1].isspace()):
            while i < n and text[i] != "\n":
                i += 1
            continue
        if text.startswith("$(", i) or c == "`":
            close = ")" if c == "$" else "`"
            depth = 1
            j = i + (2 if c == "$" else 1)
            start = j
            while j < n and depth:
                if close == ")" and text.startswith("$(", j):
                    depth += 1
                    j += 2
                    continue
                if text[j] == close:
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            subs.append(text[start:j])
            buf.append("SUBST")
            i = j + 1
            continue
        if text.startswith("&&", i) or text.startswith("||", i) or text.startswith(";;", i):
            flush(new_pipeline=True)
            i += 2
            continue
        if c in ";\n&":
            flush(new_pipeline=True)
            i += 1
            continue
        if c == "|":
            flush(new_pipeline=False)
            i += 1
            continue
        buf.append(c)
        i += 1
    flush(new_pipeline=False)
    return [p for p in pipelines if p], subs


def _tokens(segment: str) -> list[str]:
    try:
        return shlex.split(segment, posix=True)
    except ValueError:
        return segment.split()


def _carrier_inner(tokens: list[str]) -> list[str]:
    """If tokens run another command, return the inner command strings."""
    words = list(tokens)
    while words and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", words[0]):
        words.pop(0)
    if not words:
        return []
    head = words[0].rsplit("/", 1)[-1]
    rest = words[1:]
    if head in ("sudo", "doas", "nohup", "nice", "command", "exec", "builtin", "time"):
        # only the wrapper's own leading options go; the inner command keeps its flags
        valued = {"-u", "-g", "-n"} if head in ("sudo", "nice") else set()
        j = 0
        while j < len(rest) and rest[j].startswith("-"):
            j += 2 if rest[j] in valued else 1
        return [shlex.join(rest[j:])] if rest[j:] else []
    if head == "timeout":
        j = 0
        while j < len(rest) and rest[j].startswith("-"):
            j += 2 if rest[j] in ("-k", "-s", "--kill-after", "--signal") else 1
        return [shlex.join(rest[j + 1 :])] if len(rest) > j + 1 else []
    if head == "env":
        j = 0
        while j < len(rest) and (rest[j].startswith("-") or "=" in rest[j]):
            j += 1
        return [shlex.join(rest[j:])] if rest[j:] else []
    if head == "ssh":
        # skip options (those with values take the next word) and the host
        j = 0
        while j < len(rest) and rest[j].startswith("-"):
            j += (
                2
                if rest[j] in ("-i", "-p", "-l", "-o", "-F", "-J", "-L", "-R", "-D", "-W")
                and len(rest[j]) == 2
                else 1
            )
        inner = rest[j + 1 :]
        return [" ".join(inner)] if inner else []
    if head in _SHELLS or head == "su":
        for j, w in enumerate(rest):
            if w == "-c" and j + 1 < len(rest):
                return [rest[j + 1]]
        return []
    if head == "nix":
        for j, w in enumerate(rest):
            if w in ("-c", "--command") and j + 1 < len(rest):
                return [shlex.join(rest[j + 1 :])]
            if w == "--run" and j + 1 < len(rest):
                return [rest[j + 1]]
        return []
    if head == "nix-shell":
        for j, w in enumerate(rest):
            if w in ("--run", "--command") and j + 1 < len(rest):
                return [rest[j + 1]]
        return []
    if head == "busybox":
        return [shlex.join(rest)] if rest else []
    if head in ("xargs", "watch"):
        valued = {"-I", "-n", "-P", "-d", "-a", "-s", "-L"} if head == "xargs" else {"-n", "-d"}
        j = 0
        while j < len(rest) and rest[j].startswith("-"):
            j += 2 if rest[j] in valued else 1
        return [shlex.join(rest[j:])] if rest[j:] else []
    if head == "eval":
        return [" ".join(rest)] if rest else []
    return []


def commands(text: str, _depth: int = 0) -> list[Command]:
    """Every simple command `text` would run, carriers and substitutions included."""
    out: list[Command] = []
    if _depth > 6 or not text.strip():
        return out
    cleaned = strip_heredocs(text)
    pipelines, subs = _split(cleaned)
    for pipeline in pipelines:
        views = [" ".join(_tokens(seg)) for seg in pipeline]
        joined = " | ".join(views)
        for seg, view in zip(pipeline, views, strict=True):
            out.append(Command(view=view, pipeline=joined, raw=seg))
            for inner in _carrier_inner(_tokens(seg)):
                out.extend(commands(inner, _depth + 1))
    for sub in subs:
        out.extend(commands(sub, _depth + 1))
    return out
