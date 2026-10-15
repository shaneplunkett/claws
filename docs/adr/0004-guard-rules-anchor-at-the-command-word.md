---
status: accepted
---

# Guard rules match parsed commands, anchored at the command word

The inspiration repo, and the first cut of dangerous-commands, ran every rule as a bare regex over the raw command string. That blocks `git commit -m "rm -rf /"`, a memory note that mentions an infra command, and any heredoc that quotes a dangerous word. It bapped its own author three times in one afternoon. `core/shell.py` now splits a command line into the simple commands it would run (on `;`, `&&`, `|`, newlines and `$(...)`), drops heredoc bodies and comments, unquotes tokens, and recurses into carriers such as `ssh host '...'`, `bash -c '...'`, `sudo`, `timeout` and `nix develop -c`. Rules default to a `command` scope: anchored at the command word of each simple command, with the usual prefixes allowed in front. A few rules opt into wider scopes: `segment` for redirect targets, `pipeline` for `curl | sh`, `raw` for SQL inside quotes and fork bombs.

## Considered options

- Keep raw regexes and add exclusions for quoting. Rejected: every exclusion is a bypass, and there is no end to them.
- A full shell parser. Rejected: bash grammar is enormous and the guard only needs to know where commands start.

## Consequences

- Quoted prose cannot trip a `command` rule. An agent can still run the real thing through a carrier the parser knows about, and that is caught.
- A carrier the parser does not know about (`docker exec`, `kubectl exec`, a custom wrapper) hides its inner command from `command` rules. Add it to `_carrier_inner` when it matters.
- `segment` rules can still be tripped by prose, since they only know the command's unquoted tokens. Keep that scope for patterns that cannot appear in prose, like `> /dev/sda`.
- The parser is deliberately lenient. Unbalanced quotes fall back to whitespace splitting, which errs towards matching.
