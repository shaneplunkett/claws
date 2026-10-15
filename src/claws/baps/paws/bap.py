"""paws: paws off the dangerous stuff.

A PreToolUse guard for shell commands and file edits. Rules have a level;
`level` sets the lowest level that triggers. A triggered rule denies unless
its level is in `ask`, except levels in `deny` always deny.

Options (all optional):
  level: "critical" | "high" | "medium" | "low"     default "high"
  ask:   true | false | [levels]                     default false
  deny:  [levels] that deny even when ask is on      default ["critical"]
  disable: [rule ids] to switch off
  allow: [regexes]; a command matching one is never blocked
  rules: [{id, level, pattern, reason, tools?}] extra rules; tools defaults to ["shell"]
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ...core.events import Decision, Event
from ...core.jsontypes import Json, JsonObject, as_object, as_str, as_str_list
from ...core.registry import Bap

EVENT = "PreToolUse"

LEVELS = ("critical", "high", "medium", "low")
RANK = {name: i for i, name in enumerate(LEVELS)}

DEFAULTS: JsonObject = {
    "level": "high",
    "ask": False,
    "deny": ["critical"],
    "disable": [],
    "allow": [],
    "rules": [],
}


@dataclass(frozen=True)
class Rule:
    id: str
    level: str
    pattern: str
    reason: str
    tools: tuple[str, ...] = ("shell",)

    def regex(self) -> re.Pattern[str]:
        return re.compile(self.pattern, re.DOTALL)


_DEV = r"/dev/(sd[a-z]|nvme\d|hd[a-z]|vd[a-z]|xvd[a-z]|mmcblk\d|disk\d)"
_HOOK_FILES = r"(\.claws\.json|\.claude/settings(\.local)?\.json|\.codex/(hooks\.json|config\.toml))"
_PVE_VERBS = r"(create|destroy|start|stop|shutdown|reboot|reset|suspend|resume|migrate|clone|set|resize|importdisk|move_disk|move-disk|disk\s+move|delsnapshot|rollback|template)"

# fmt: off
BUILTIN: tuple[Rule, ...] = (
    # critical: unrecoverable
    Rule("rm-home", "critical", r"\brm\s+(-\S+\s+)*[\"']?(~/?|\$HOME/?)[\"']?(\s|$|[;&|])", "rm targeting the home directory"),
    Rule("rm-root", "critical", r"\brm\s+(-\S+\s+)*[\"']?/[\"']?(\*|\s|$|[;&|])", "rm targeting the root filesystem"),
    Rule("rm-system", "critical", r"\brm\s+(-\S+\s+)*/(etc|usr|var|bin|sbin|lib|lib64|boot|dev|proc|sys|nix|opt|home)(/|\s|$)", "rm targeting a system directory"),
    Rule("rm-cwd", "critical", r"\brm\s+(-\S+\s+)*(\./?|\*|\./\*)(\s|$|[;&|])", "rm of the whole current directory"),
    Rule("dd-disk", "critical", r"\bdd\b.*\bof=" + _DEV, "dd writing straight to a disk"),
    Rule("mkfs", "critical", r"\bmkfs(\.\w+)?\b.*" + _DEV, "formatting a disk"),
    Rule("disk-redirect", "critical", r">\s*" + _DEV, "shell redirect onto a disk device"),
    Rule("fork-bomb", "critical", r":\(\)\s*\{.*:\s*\|\s*:.*&", "fork bomb"),
    Rule("chmod-root", "critical", r"\b(chmod|chown)\s+(-\S+\s+)*-R\b.*\s/(\s|$)|\b(chmod|chown)\s+-R\s+\S+\s+/(\s|$)", "recursive chmod/chown of /"),
    Rule("zfs-destroy", "critical", r"\b(zfs|zpool)\s+destroy\b", "destroying a ZFS dataset or pool"),
    Rule("lvm-remove", "critical", r"\b(lvremove|vgremove|pvremove|wipefs)\b", "removing an LVM volume or wiping signatures"),
    # high: data loss, bypassing process, infra changes outside the PR flow
    Rule("curl-pipe-sh", "high", r"\b(curl|wget)\b.*\|\s*(sudo\s+)?(ba|z|da)?sh\b", "piping a download into a shell"),
    Rule("git-force-main", "high", r"\bgit\s+push\b(?!.*--force-with-lease).*(--force|\s-f)\b.*\b(main|master)\b", "force push to main/master"),
    Rule("git-push-main", "high", r"\bgit\s+push\b.*\b(origin|upstream)\s+(\S+:)?(main|master)\b|\bgit\s+push\b.*\bHEAD:(main|master)\b", "pushing straight to main/master, that is what PRs are for"),
    Rule("git-reset-hard", "high", r"\bgit\s+reset\s+(-\S+\s+)*--hard\b", "git reset --hard throws away uncommitted work"),
    Rule("git-clean-f", "high", r"\bgit\s+clean\s+(-\w*f|-f|--force)", "git clean -f deletes untracked files"),
    Rule("git-branch-D", "high", r"\bgit\s+branch\s+(-\S+\s+)*(-D|--delete\s+--force|-d\s+-f)\b", "force deleting a branch"),
    Rule("chmod-777", "high", r"\bchmod\b.*\b777\b", "chmod 777"),
    Rule("docker-volume-rm", "high", r"\bdocker\s+volume\s+(rm|prune)\b", "deleting docker volumes"),
    Rule("terraform-apply", "high", r"\b(terraform|tofu)\s+(-\S+\s+)*(apply|destroy|import|taint|untaint|state\s+(rm|mv|push)|force-unlock)\b", "terraform/tofu changing real infra; that lands by PR"),
    Rule("pve-mutate", "high", r"\b(qm|pct|pvesh|pvesm|pvecm|pveum)\s+(-\S+\s+)*" + _PVE_VERBS + r"\b|\bpvesh\s+(create|set|delete)\b", "Proxmox change outside Terraform; it will drift"),
    Rule("nix-switch", "high", r"\b(nixos-rebuild|darwin-rebuild)\s+(-\S+\s+)*(switch|boot)\b|\bnh\s+(os|darwin|home)\s+(switch|boot)\b|\bcolmena\s+apply(-local)?\b|\bhome-manager\s+switch\b", "switching a system generation; Shane does that by hand"),
    Rule("systemctl-mutate", "high", r"\bsystemctl\s+(-\S+\s+)*(stop|restart|disable|mask|kill|isolate|poweroff|reboot|halt)\b", "stopping or restarting a service"),
    Rule("power", "high", r"\b(shutdown|reboot|poweroff|halt|init\s+[06])\b(?!\s*=)", "powering a machine off or rebooting it"),
    # Only a writing command with the file as a direct argument (no pipe or ; in between), or a redirect onto it.
    # A python or jq invocation that merely mentions the path is not a write; it bapped the author mid-heredoc.
    Rule("hook-config-tamper", "high", r"(\b(sed\s+-i|tee|rm|mv|cp|truncate)\b[^;|&\n]*|>+\s*)" + _HOOK_FILES, "rewriting agent hook config"),
    Rule("hook-config-edit", "high", _HOOK_FILES + r"$", "editing agent hook config", tools=("edit",)),
    # medium: context dependent
    Rule("git-force-any", "medium", r"\bgit\s+push\b(?!.*--force-with-lease).*(--force|\s-f)\b", "force push; use --force-with-lease"),
    Rule("git-checkout-dot", "medium", r"\bgit\s+(checkout|restore)\s+(--\s+)?\.(\s|$)", "discarding all working tree changes"),
    Rule("git-stash-drop", "medium", r"\bgit\s+stash\s+(drop|clear)\b", "dropping stashes"),
    Rule("sudo-rm", "medium", r"\bsudo\s+(-\S+\s+)*rm\b", "rm as root"),
    Rule("docker-prune", "medium", r"\bdocker\s+(system|image|container|network)\s+prune\b", "docker prune"),
    Rule("kubectl-delete", "medium", r"\bkubectl\s+((-\S+|--\S+)(\s+\S+)?\s+)*delete\b", "kubectl delete"),
    Rule("sql-drop", "medium", r"(?i)\b(drop|truncate)\s+(database|table|schema)\b", "dropping a database object"),
    Rule("mount", "medium", r"\b(mount|umount|mount\.nfs)\s", "mounting or unmounting a filesystem"),
    Rule("crontab-r", "medium", r"\bcrontab\s+-r\b", "removing all cron jobs"),
    # low: worth a glance
    Rule("rm-rf", "low", r"\brm\s+(-\S*[rR]\S*\s+)", "recursive rm"),
    Rule("kill", "low", r"\b(kill\s+-9|killall|pkill)\b", "killing processes"),
)
# fmt: on


@dataclass(frozen=True)
class Options:
    """Validated paws options. Built from merged JSON config by parse_options."""

    level: str
    ask: frozenset[str]
    deny: frozenset[str]
    disable: frozenset[str]
    allow: tuple[re.Pattern[str], ...]
    rules: tuple[Rule, ...]


def _level(value: Json, what: str) -> str:
    level = as_str(value, what)
    if level not in RANK:
        raise ValueError(f"{what}: unknown level {level!r}; known: {list(LEVELS)}")
    return level


def _levels(value: Json, what: str) -> frozenset[str]:
    if value is True:
        return frozenset(LEVELS)
    if value is False or value is None:
        return frozenset()
    return frozenset(_level(v, what) for v in as_str_list(value, what))


def _rule(spec: Json) -> Rule:
    obj = as_object(spec, "rules entry")
    rule_id = as_str(obj.get("id"), "rules[].id")
    return Rule(
        id=rule_id,
        level=_level(obj.get("level", "high"), f"rule {rule_id!r} level"),
        pattern=as_str(obj.get("pattern"), f"rule {rule_id!r} pattern"),
        reason=as_str(obj.get("reason", rule_id), f"rule {rule_id!r} reason"),
        tools=tuple(as_str_list(obj.get("tools", ["shell"]), f"rule {rule_id!r} tools")),
    )


def parse_options(options: JsonObject) -> Options:
    merged = {**DEFAULTS, **options}
    rules_value = merged.get("rules") or []
    if not isinstance(rules_value, list):
        raise ValueError("rules must be a list")
    return Options(
        level=_level(merged.get("level"), "level"),
        ask=_levels(merged.get("ask"), "ask"),
        deny=_levels(merged.get("deny"), "deny"),
        disable=frozenset(as_str_list(merged.get("disable") or [], "disable")),
        allow=tuple(re.compile(p, re.DOTALL) for p in as_str_list(merged.get("allow") or [], "allow")),
        rules=tuple(_rule(spec) for spec in rules_value),
    )


def active_rules(options: Options) -> list[Rule]:
    return [
        r for r in (*BUILTIN, *options.rules) if RANK[r.level] <= RANK[options.level] and r.id not in options.disable
    ]


def match(event: Event, options: JsonObject) -> Rule | None:
    parsed = parse_options(options)
    if event.tool == "shell":
        subjects = [event.command or ""]
    elif event.tool == "edit":
        subjects = list(event.paths)
    else:
        return None
    if not any(subjects):
        return None
    for rule in active_rules(parsed):
        if event.tool not in rule.tools:
            continue
        regex = rule.regex()
        for subject in subjects:
            if regex.search(subject) and not any(a.search(subject) for a in parsed.allow):
                return rule
    return None


def run(event: Event, options: JsonObject) -> Decision:
    if event.kind != EVENT:
        return Decision.none()
    parsed = parse_options(options)
    rule = match(event, options)
    if rule is None:
        return Decision.none()
    # No trailing full stop: Codex appends ". Command: ..." to the reason.
    reason = f"🐾 bap! paws rule '{rule.id}' ({rule.level}): {rule.reason}"
    if rule.level in parsed.ask and rule.level not in parsed.deny:
        return Decision.ask(reason + ". Want to let this one through?")
    return Decision.deny(reason + ". Ask Shane before doing that")


BAP = Bap(
    name="paws",
    event=EVENT,
    tools=("shell", "edit"),
    timeout=10,
    fail_closed=True,
    defaults=DEFAULTS,
    run=run,
)
