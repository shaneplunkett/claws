---
status: accepted
---

# Every rule lives in claws, none inline

A bap set picks baps and groups, sets options such as the level, and can reword a rule's reason to fit the repo. It cannot add rules of its own. A rule a repo needs goes into claws, usually inside a group, with tests and a place in the bench. Inline rules would be the obvious escape hatch, but Shane knows a rule written into one repo's flake gets forgotten there and never makes it back to the others. Keeping every rule in claws also gives the glow-up skill one catalogue to configure repos from.

## Consequences

- A new fence means a claws change and a flake input bump, not a line in the consuming repo.
- Options that pass free-form patterns or rule lists through to a bap are a bug, not a feature.
