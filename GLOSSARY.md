# claws

Hooks for coding agents, written once and delivered to more than one agent harness. These words are also the option names: `programs.claws.bap.<bap>.groups.<group>.enable` reads straight off the glossary.

## The framework

**claws**:
The framework as a whole: the baps, the adapters that carry them to each harness, and the Nix flake that delivers them.
_Avoid_: hooks repo, plugin, toolkit

**Bap**:
One claws hook: a program a harness runs at one of its events, which reads the event payload and replies with a decision.
_Avoid_: hook (for ours; the harness-side mechanism keeps that name), plugin, guard, script

**Harness**:
A coding agent program that runs hooks, and so runs baps. Today that is Claude Code and Codex.
_Avoid_: agent, client, tool (all overloaded)

**Event**:
The point in the harness loop at which a bap runs. PreToolUse, PostToolUse, SessionStart, UserPromptSubmit, Stop.
_Avoid_: trigger, lifecycle point

**Payload**:
The JSON a harness sends to a bap on stdin for one event.
_Avoid_: input, context, request

**Matcher**:
The harness-specific pattern that picks which tool calls a bap runs for. Claude matches on tool name, Codex matches on function name.
_Avoid_: filter, selector

**Adapter**:
The per-harness code that turns a payload into a normalised event and a decision back into that harness's response. Baps never see a raw payload.
_Avoid_: shim, translator, driver

**Decision**:
What a bap says back to the harness: allow, deny with a reason that points at the right path, or add context.
_Avoid_: result, verdict, response, output

## Configuring baps

**Bap set**:
The baps a consumer has chosen to enable, with their options, for one or more harnesses.
_Avoid_: selection, profile, bundle

**Scope**:
Where a bap set is declared: global, in home-manager, or repo, in that repo's flake. Scopes don't merge: each runs its own bap set with its own options, so a bap on in both scopes runs twice, and a deny from either wins.
_Avoid_: context, layer, level

**Wiring**:
The harness config files that tell a harness to run baps: `.claude/settings.local.json` and `.codex/hooks.json` in a repo, the harness settings files globally. Nix writes them; nothing else should.
_Avoid_: install, hook config

**Installer**:
The claws program that writes a repo's wiring from its bap set, run by the dev shell.
_Avoid_: setup script, bootstrap, sync

## Rules

**Rule**:
One pattern a bap checks, with the reason it gives when the pattern matches. Every rule lives in claws.
_Avoid_: check, pattern, policy

**Floor**:
The rules of a bap that are always on and that no scope can switch off.
_Avoid_: defaults, baseline, core rules

**Level**:
How much of a bap's floor applies: critical, high or strict, each including the ones before it.
_Avoid_: severity, mode, strictness

**Group**:
A named bundle of a bap's rules for one CLI or workflow, such as tofu, proxmox or gh, switched on per scope.
_Avoid_: pack, category, ruleset, preset

## Performance

**Budget**:
The most a bap may cost on one event beyond bare Python startup, declared by the bap itself as a multiple of that startup. It counts everything claws does on the bap's behalf, not just the bap's own work.
_Avoid_: limit, SLA, timeout (the harness's kill switch is a separate thing)

**Bench**:
The claws benchmark that runs each bap against captured payloads and checks it against its budget.
_Avoid_: perf test, profiler
