---
status: accepted
---

# One adapter per harness, baps never see raw payloads

Claude Code and Codex share event names and a near-identical response schema (`hookSpecificOutput.permissionDecision` with allow, deny, ask, plus `additionalContext` and `continue`). They differ in how they name tools (Bash versus exec_command, Edit versus apply_patch), where the command string lives (`tool_input.command` versus `tool_input.cmd`), and which config file holds the hook list. Rather than let every bap branch on a harness flag, as the caboodle hooks do now, each harness gets an adapter module. It parses the payload into a normalised event (kind, tool class, command, file paths) and renders a decision back into that harness's wire format. Baps are pure functions from event to decision.

## Consequences

- Adding a harness means writing one adapter and capturing fixtures. Baps do not change.
- Every adapter ships with real captured payloads under `src/claws/fixtures/<harness>/`, one per event and tool class. Adapter tests run against those, not against hand-written JSON.
- The normalised event is the stable contract inside the repo. Changing it touches every bap, so change it rarely.
