"""dangerous-commands: paws off the dangerous stuff.

A PreToolUse guard for shell commands and file edits. Rules have a level;
`level` sets the lowest level that triggers. A triggered rule always denies;
baps never ask (ADR 0006).

Options (all optional):
  level: "critical" | "high" | "medium" | "low"     default "high"
  disable: [rule ids] to switch off
  allow: [regexes]; a command matching one is never blocked
  rules: [{id, level, pattern, reason, tools?, scope?}] extra rules; tools defaults to ["shell"],
         scope to "segment" (anywhere in one unquoted simple command). See Rule for the scopes.

The retired `ask`, `deny` and `unattended` options are ignored, not rejected.
This bap fails closed, so rejecting a key an old config still sets would deny
every shell command.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from ...core import shell
from ...core.events import Decision, Event
from ...core.jsontypes import Json, JsonObject, as_object, as_str, as_str_list
from ...core.registry import Bap

EVENT = "PreToolUse"

LEVELS = ("critical", "high", "medium", "low")
RANK = {name: i for i, name in enumerate(LEVELS)}

DEFAULTS: JsonObject = {
    "level": "high",
    "disable": [],
    "allow": [],
    "rules": [],
}


Scope = Literal["command", "segment", "pipeline", "raw"]


@dataclass(frozen=True)
class Rule:
    """A pattern at a level, matched at a scope.

    command:  anchored at the command word of each simple command, after any
              sudo/env/timeout-style prefix. Quoted prose elsewhere cannot match.
    segment:  anywhere in one simple command's unquoted view (redirect targets).
    pipeline: anywhere in a whole pipeline's view (curl | sh).
    raw:      anywhere in the raw text (SQL inside quotes, fork bombs).
    """

    id: str
    level: str
    pattern: str
    reason: str
    tools: tuple[str, ...] = ("shell",)
    scope: Scope = "command"

    def regex(self) -> re.Pattern[str]:
        if self.scope == "command":
            return re.compile(
                shell.PREFIXES.pattern + shell.COMMAND_PATH + "(?:" + self.pattern + ")", re.DOTALL
            )
        return re.compile(self.pattern, re.DOTALL)


_DEV = (
    r"/dev/(sd[a-z]+|nvme\d+(n\d+)?|hd[a-z]+|vd[a-z]+|xvd[a-z]+|mmcblk\d+|disk\d+|mapper/\S+|md\d+|dm-\d+|loop\d+"
    r"|nbd\d+|rbd\d+|zd\d+|disk/by-(id|uuid|path|label|partuuid|partlabel)/\S+)"
)
# The files, and the directories that hold them: renaming .codex away disables the hooks
# just as well.
_HOOK_FILES = (
    r"(\.claws\.json|\.claude(/settings(\.local)?\.json)?|\.codex(/(hooks\.json|config\.toml))?)"
)
_SYSTEM_DIRS = r"(etc|usr|var|bin|sbin|lib|lib64|boot|dev|proc|sys|nix|opt|home|root|srv)"
# git's global options sit between `git` and the subcommand: git -C repo --no-pager push ...
_GIT = (
    r"git\s+(?:(?:-C|-c|--git-dir|--work-tree|--namespace|--exec-path)\s+\S+\s+"
    r"|--?[\w-]+(?:=\S*)?\s+)*"
)
_PVE_VERBS = (
    r"(create|destroy|start|stop|shutdown|reboot|reset|suspend|resume|migrate|clone|set|resize"
    r"|importdisk|move_disk|move-disk|disk\s+move|delsnapshot|rollback|template)"
)

BUILTIN: tuple[Rule, ...] = (
    # Rules default to scope "command": anchored at the command word of each simple command
    # (sudo, env, timeout and friends allowed in front), after unquoting. Prose in a quoted
    # argument of some other command cannot match. See core/shell.py.
    #
    # critical: unrecoverable
    Rule(
        "rm-home",
        "critical",
        r"rm\s+(-\S+\s+)*(\S+\s+)*(~/?|\$HOME/?|\$\{HOME\}/?)(\s|$)",
        "rm targeting the home directory",
    ),
    Rule(
        "rm-root",
        "critical",
        r"rm\s+(-\S+\s+)*(\S+\s+)*/(\*|\s|$)",
        "rm targeting the root filesystem",
    ),
    Rule(
        "rm-system",
        "critical",
        r"rm\s+(-\S+\s+)*(\S+\s+)*/" + _SYSTEM_DIRS + r"(/|\s|$)",
        "rm targeting a system directory",
    ),
    Rule(
        "rm-cwd",
        "critical",
        r"rm\s+(-\S+\s+)*(\S+\s+)*(\./?|\*|\./\*)(\s|$)",
        "rm of the whole current directory",
    ),
    Rule("dd-disk", "critical", r"dd\b.*\bof=" + _DEV, "dd writing straight to a disk"),
    Rule("mkfs", "critical", r"mkfs(\.\w+)?\b.*" + _DEV, "formatting a disk"),
    Rule(
        "disk-redirect",
        "critical",
        r">\s*" + _DEV,
        "shell redirect onto a disk device",
        scope="segment",
    ),
    Rule(
        "disk-write",
        "critical",
        r"(cp|tee|install)\s+(\S+\s+)*" + _DEV + r"(\s|$)",
        "writing a file straight onto a disk",
    ),
    Rule(
        "find-delete", "high", r"find\s+.*\s(-delete|-exec\s+rm)\b", "find deleting what it matches"
    ),
    Rule("fork-bomb", "critical", r":\(\)\s*\{.*:\s*\|\s*:.*&", "fork bomb", scope="raw"),
    Rule(
        "chmod-system",
        "critical",
        r"(chmod|chown)\s+(\S+\s+)*(-\S*R\S*|--recursive)\b.*\s/(" + _SYSTEM_DIRS + r")?/?(\s|$)",
        "recursive chmod/chown of / or a system directory",
    ),
    Rule("zfs-destroy", "critical", r"(zfs|zpool)\s+destroy\b", "destroying a ZFS dataset or pool"),
    Rule(
        "disk-wipe",
        "critical",
        r"(lvremove|vgremove|pvremove|wipefs|blkdiscard)\b|sgdisk\b.*\s(-Z|--zap-all|-z|--zap|-o|--clear)\b|shred\b.*"
        + _DEV,
        "wiping a disk, volume or partition table",
    ),
    # high: data loss, bypassing process, infra changes outside the PR flow
    Rule(
        "curl-pipe-sh",
        "high",
        r"\b(curl|wget)\b.*\|\s*(sudo\s+)?(ba|z|da)?sh\b",
        "piping a download into a shell",
        scope="pipeline",
    ),
    Rule(
        "git-force-main",
        "high",
        _GIT + r"push\b(?!.*--force-with-lease).*(--force|\s-f)\b.*\b(main|master)\b",
        "force push to main/master",
    ),
    Rule(
        "git-push-main",
        "high",
        _GIT
        + r"push\b.*\b(origin|upstream)\s+(\S+:)?(main|master)\b|"
        + _GIT
        + r"push\b.*\bHEAD:(main|master)\b",
        "pushing straight to main/master, that is what PRs are for",
    ),
    Rule(
        "git-delete-main",
        "high",
        _GIT
        + r"push\b.*(--delete\s+(main|master)\b|:refs/heads/(main|master)\b"
        + r"|\s:(main|master)(\s|$))|"
        + _GIT
        + r"update-ref\s+-d\s+refs/heads/(main|master)\b",
        "deleting main/master on the remote",
    ),
    Rule(
        "git-reset-hard",
        "high",
        _GIT + r"reset\s+(-\S+\s+)*--hard\b",
        "git reset --hard throws away uncommitted work",
    ),
    Rule(
        "git-clean-f",
        "high",
        _GIT + r"clean\s+(-\w*f|-f|--force)",
        "git clean -f deletes untracked files",
    ),
    Rule(
        "git-branch-D",
        "high",
        _GIT + r"branch\s+(-\S+\s+)*(-D|--delete\s+--force|-d\s+-f)\b",
        "force deleting a branch",
    ),
    Rule("chmod-777", "high", r"chmod\b.*\b777\b", "chmod 777"),
    Rule(
        "docker-volume-rm",
        "high",
        r"docker\s+volume\s+(rm|prune)\b|docker(-compose|\s+compose)\b.*\bdown\b.*(\s-v|--volumes)\b",
        "deleting docker volumes",
    ),
    Rule(
        "terraform-apply",
        "high",
        r"(terraform|tofu)\s+(-\S+\s+)*(apply|destroy|import|taint|untaint|state\s+(rm|mv|push)|force-unlock)\b",
        "terraform/tofu changing real infra; that lands by PR",
    ),
    Rule(
        "pve-mutate",
        "high",
        r"(qm|pct|pvesh|pvesm|pvecm|pveum)\s+(-\S+\s+)*"
        + _PVE_VERBS
        + r"\b|pvesh\s+(create|set|delete)\b",
        "Proxmox change outside Terraform; it will drift",
    ),
    Rule(
        "nix-switch",
        "high",
        r"(nixos-rebuild|darwin-rebuild)\s+(-\S+\s+)*(switch|boot)\b|nh\s+(os|darwin|home)\s+(switch|boot)\b|colmena\s+apply(-local)?\b|home-manager\s+switch\b",
        "switching a system generation; Shane does that by hand",
    ),
    Rule(
        "systemctl-mutate",
        "high",
        r"systemctl\s+(-\S+\s+)*(stop|restart|disable|mask|kill|isolate|poweroff|reboot|halt)\b|(service|rc-service)\s+\S+\s+(stop|restart)\b",
        "stopping or restarting a service",
    ),
    Rule(
        "power",
        "high",
        r"(shutdown|reboot|poweroff|halt|init\s+[06])\b",
        "powering a machine off or rebooting it",
    ),
    Rule(
        "hook-config-tamper",
        "high",
        r"(sed\s+-i|tee|rm|rmdir|mv|cp|install|ln|truncate|chmod|chown|chattr)\b.*[\s/]"
        + _HOOK_FILES
        + r"(?=\s|$)",
        "rewriting, replacing, hiding or renaming agent hook config",
    ),
    Rule(
        "hook-config-redirect",
        "high",
        r">+\s*" + _HOOK_FILES + r"(?=\s|$)",
        "redirecting output onto agent hook config",
        scope="segment",
    ),
    Rule(
        "hook-config-edit", "high", _HOOK_FILES + r"$", "editing agent hook config", tools=("edit",)
    ),
    # medium: context dependent
    Rule(
        "git-force-any",
        "medium",
        _GIT + r"push\b(?!.*--force-with-lease).*(--force|\s-f)\b",
        "force push; use --force-with-lease",
    ),
    Rule(
        "git-checkout-dot",
        "medium",
        _GIT + r"(checkout|restore)\s+(--\s+)?\.(\s|$)",
        "discarding all working tree changes",
    ),
    Rule("git-stash-drop", "medium", _GIT + r"stash\s+(drop|clear)\b", "dropping stashes"),
    Rule("sudo-rm", "medium", r"sudo\s+(-\S+\s+)*rm\b", "rm as root"),
    Rule(
        "docker-prune",
        "medium",
        r"docker\s+(system|image|container|network)\s+prune\b",
        "docker prune",
    ),
    Rule(
        "kubectl-delete",
        "medium",
        r"kubectl\s+((-\S+|--\S+)(\s+\S+)?\s+)*delete\b",
        "kubectl delete",
    ),
    Rule(
        "sql-drop",
        "medium",
        r"(?i)\b(drop|truncate)\s+(database|table|schema)\b",
        "dropping a database object",
        scope="raw",
    ),
    Rule("mount", "medium", r"(mount|umount|mount\.nfs)\s", "mounting or unmounting a filesystem"),
    Rule("crontab-r", "medium", r"crontab\s+-r\b", "removing all cron jobs"),
    # low: worth a glance
    Rule("rm-rf", "low", r"rm\s+(-\S*[rR]\S*)(\s|$)", "recursive rm"),
    Rule("kill", "low", r"(kill\s+-9|killall|pkill)\b", "killing processes"),
)


@dataclass(frozen=True)
class Options:
    """Validated dangerous-commands options. Built from merged JSON config by parse_options."""

    level: str
    disable: frozenset[str]
    allow: tuple[re.Pattern[str], ...]
    rules: tuple[Rule, ...]


def _level(value: Json, what: str) -> str:
    level = as_str(value, what)
    if level not in RANK:
        raise ValueError(f"{what}: unknown level {level!r}; known: {list(LEVELS)}")
    return level


def _rule(spec: Json) -> Rule:
    obj = as_object(spec, "rules entry")
    rule_id = as_str(obj.get("id"), "rules[].id")
    return Rule(
        id=rule_id,
        level=_level(obj.get("level", "high"), f"rule {rule_id!r} level"),
        pattern=as_str(obj.get("pattern"), f"rule {rule_id!r} pattern"),
        reason=as_str(obj.get("reason", rule_id), f"rule {rule_id!r} reason"),
        tools=tuple(as_str_list(obj.get("tools", ["shell"]), f"rule {rule_id!r} tools")),
        scope=_scope(obj.get("scope", "segment"), f"rule {rule_id!r} scope"),
    )


def _scope(value: Json, what: str) -> Scope:
    scope = as_str(value, what)
    if scope == "command":
        return "command"
    if scope == "segment":
        return "segment"
    if scope == "pipeline":
        return "pipeline"
    if scope == "raw":
        return "raw"
    raise ValueError(f"{what}: unknown scope {scope!r}; known: command, segment, pipeline, raw")


def parse_options(options: JsonObject) -> Options:
    merged = {**DEFAULTS, **options}
    rules_value = merged.get("rules") or []
    if not isinstance(rules_value, list):
        raise ValueError("rules must be a list")
    return Options(
        level=_level(merged.get("level"), "level"),
        disable=frozenset(as_str_list(merged.get("disable") or [], "disable")),
        allow=tuple(
            re.compile(p, re.DOTALL) for p in as_str_list(merged.get("allow") or [], "allow")
        ),
        rules=tuple(_rule(spec) for spec in rules_value),
    )


def active_rules(options: Options) -> list[Rule]:
    return [
        r
        for r in (*BUILTIN, *options.rules)
        if RANK[r.level] <= RANK[options.level] and r.id not in options.disable
    ]


def subjects_for(rule: Rule, event: Event, parsed_commands: list[shell.Command]) -> list[str]:
    """What text a rule looks at, by tool class and scope."""
    if event.tool == "edit":
        return list(event.paths)
    if rule.scope == "raw":
        return [event.command or ""]
    if rule.scope == "pipeline":
        return sorted({c.pipeline for c in parsed_commands})
    return [c.view for c in parsed_commands]


def match(event: Event, options: JsonObject) -> Rule | None:
    parsed = parse_options(options)
    if event.tool == "shell":
        if not event.command:
            return None
        parsed_commands = shell.commands(event.command)
    elif event.tool == "edit":
        if not event.paths:
            return None
        parsed_commands = []
    else:
        return None
    for rule in active_rules(parsed):
        if event.tool not in rule.tools:
            continue
        # edit subjects are paths, not command lines; never anchor those
        regex = rule.regex() if event.tool == "shell" else re.compile(rule.pattern, re.DOTALL)
        for subject in subjects_for(rule, event, parsed_commands):
            if regex.search(subject) and not any(a.search(subject) for a in parsed.allow):
                return rule
    return None


def run(event: Event, options: JsonObject) -> Decision:
    if event.kind != EVENT:
        return Decision.none()
    rule = match(event, options)
    if rule is None:
        return Decision.none()
    # No trailing full stop: Codex appends ". Command: ..." to the reason.
    reason = f"🐾 bap! dangerous-commands rule '{rule.id}' ({rule.level}): {rule.reason}"
    return Decision.deny(reason + ". Ask Shane before doing that")


BAP = Bap(
    name="dangerous-commands",
    event=EVENT,
    tools=("shell", "edit"),
    timeout=10,
    fail_closed=True,
    defaults=DEFAULTS,
    run=run,
)
