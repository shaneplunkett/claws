---
status: accepted
---

# Baps never ask

Both harnesses accept an "ask" decision that prompts the user before a tool call runs, and the first cut of dangerous-commands used it. In practice Shane runs Claude Code and Codex with permissions bypassed, often under T3 Code, and in those modes there is nobody to answer the prompt: it is either skipped or turns into a refusal the agent can't act on. So a bap's decision is allow, deny with a reason that tells the agent the right path, or add context. A deny is the stronger answer anyway, because its reason redirects the agent where an ask only stops it.

## Consequences

- No bap option enables ask, and the adapters only render allow, deny and context.
- Anything that once warranted an ask is either a deny with a redirect or not a rule at all.
