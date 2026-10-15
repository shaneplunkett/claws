# claws

Hooks for coding agents, written once and delivered to more than one agent harness.

## Language

**Harness**:
A coding agent program that runs hooks, and so runs baps. Today that is Claude Code and Codex.
_Avoid_: agent, client, tool (all overloaded)

**Bap**:
One claws hook: a program a harness runs at one of its events, which reads the event payload and replies with a decision.
_Avoid_: hook (for ours; the harness-side mechanism keeps that name), plugin, guard, script

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
What a bap says back to the harness. Allow, deny, ask, or add context, with an optional reason.
_Avoid_: result, verdict, response, output

**Bap set**:
The baps a consumer has chosen to enable, with their options, for one or more harnesses.
_Avoid_: selection, profile, bundle

**Installer**:
The flake app that writes a bap set into a repo's project-level hook config files.
_Avoid_: setup script, bootstrap
