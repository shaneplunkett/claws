# Per-repo manifests for agent skills and hooks: design need or npx artefact?

- **Question:** Is a per-repo manifest/installer (like claws' `nix run .#install` writing `.claws.json`) a genuine design need, or mostly a consequence of distributing via npx, where there's no declarative config layer so a file in the repo is the only place to record what was installed? Should claws drop the installer and `.claws.json` for a "mine first, Nix only, no inline custom rules" setup?
- **Researched:** 2026-10-16, normal

## Sub-questions

1. What Vercel's skills tooling (`npx skills`, skills.sh) writes into a repo, and why: answered
2. What Matt Pocock's skills distribution does, and why: answered
3. How hook-specific projects (karanb192/claude-code-hooks, Claude Code plugin marketplaces, committed `.claude/settings.json`) record per-repo config: answered
4. The underlying reasons per-repo manifests exist, and which a Nix flake declaration already covers: answered

## Claims

- `npx skills add` at project scope (the default) writes a `skills-lock.json` at the repo root, intended to be checked into version control.
  - Source: https://github.com/vercel-labs/skills/blob/main/src/local-lock.ts
  - Date: 2026-04-27 (last change); introduced 2026-02-20
  - Verdict: confirmed
- Each `skills-lock.json` entry records source, optional ref, source type, skill path and a SHA-256 `computedHash` of the skill files; entries are timestamp-free and sorted so branches adding different skills merge cleanly.
  - Source: https://github.com/vercel-labs/skills/blob/main/src/local-lock.ts
  - Date: 2026-04-27
  - Verdict: confirmed
- The project lock arrived in PR #401 for "deterministic and merge-friendly tracking of project-specific skills", alongside syncing skills from `node_modules`.
  - Source: https://github.com/vercel-labs/skills/pull/401
  - Date: 2026-02-20
  - Verdict: confirmed
- `skills install` with no arguments (alias of `experimental_install`) restores skills from `skills-lock.json`, an `npm ci` equivalent.
  - Source: https://github.com/vercel-labs/skills/blob/main/AGENTS.md
  - Date: undated (repo at v1.7.2, 2026-10-09)
  - Verdict: confirmed (feature requested in issue #549, 2026-03-08)
- Separately, global installs are tracked in `~/.agents/.skill-lock.json`, which `skills check`/`update` read to compare GitHub tree SHAs and detect updates.
  - Source: https://github.com/vercel-labs/skills/blob/main/AGENTS.md
  - Date: undated (repo at v1.7.2, 2026-10-09)
  - Verdict: confirmed
- The README pitches project scope as "committed with your project, shared with team".
  - Source: https://github.com/vercel-labs/skills/blob/main/README.md
  - Date: undated (repo at v1.7.2, 2026-10-09)
  - Verdict: confirmed
- Vercel skills now also reads a declarative `skills` field in `package.json` (antfu skills-npm SPEC), so a package can declare which skills it wants without shipping them.
  - Source: https://github.com/vercel-labs/skills/pull/2400
  - Date: 2026-10-07
  - Verdict: confirmed
- Matt Pocock's skills install through Vercel's `npx skills` only as the fallback "any other agent, or editable files" path; that path copies files you update by hand (`npx skills@latest update`).
  - Source: https://github.com/mattpocock/skills/blob/main/README.md
  - Date: 2026-10-08
  - Verdict: confirmed
- Matt Pocock's primary install for Claude Code, Codex and Copilot is now a native plugin that updates itself (Claude: `claude plugin install mattpocock-skills@claude-plugins-official`).
  - Source: https://github.com/mattpocock/skills/blob/main/README.md
  - Date: 2026-10-08; plugin shipped 2026-07-13
  - Verdict: confirmed (superseded the npx-first README of 2026-03-18)
- `/setup-matt-pocock-skills` runs once per repo and writes repo-specific config (issue tracker, triage labels, domain-doc layout) into files like `docs/agents/issue-tracker.md`; it is configuration for the skills, not a record of what was installed.
  - Source: https://github.com/mattpocock/skills/blob/main/skills/engineering/setup-matt-pocock-skills/SKILL.md
  - Date: 2026-10-07
  - Verdict: confirmed
- Matt Pocock's `git-guardrails-claude-code` skill installs a hook by copying a script into `.claude/hooks/` and wiring it into `.claude/settings.json` (project) or `~/.claude/settings.json` (global); no separate manifest.
  - Source: https://github.com/mattpocock/skills/blob/main/skills/misc/git-guardrails-claude-code/SKILL.md
  - Date: 2026-08-19
  - Verdict: confirmed
- karanb192/claude-code-hooks ships 22 hooks as a Claude Code plugin marketplace (`/plugin marketplace add`, `/plugin install`), with a fallback of copying the script and wiring `settings.json` by hand; it has no manifest of its own.
  - Source: https://github.com/karanb192/claude-code-hooks
  - Date: 2026-10-04 (last push)
  - Verdict: confirmed
- Claude Code project-scope plugins are recorded in the committed `.claude/settings.json` under `enabledPlugins`; committing turns the plugin on for collaborators but does not download it, so each runs `claude plugin install --scope project` once.
  - Source: https://code.claude.com/docs/en/discover-plugins
  - Date: undated (fetched 2026-10-16)
  - Verdict: confirmed
- A repo's `.claude/settings.json` can register marketplaces via `extraKnownMarketplaces`, which applies only after each teammate trusts the folder.
  - Source: https://code.claude.com/docs/en/settings
  - Date: undated (fetched 2026-10-16)
  - Verdict: confirmed
- Claude Code marketplaces can be pinned to a git ref with `owner/repo#ref`.
  - Source: https://code.claude.com/docs/en/discover-plugins
  - Date: undated (fetched 2026-10-16)
  - Verdict: confirmed
- Nix generates `flake.lock`, mapping each unlocked input in `flake.nix` to a locked revision, for reproducibility.
  - Source: https://nix.dev/manual/nix/latest/command-ref/new-cli/nix3-flake.html
  - Date: Nix 2.35.2 manual (undated page)
  - Verdict: confirmed

## Synthesis

The per-repo files split into two kinds:

- **Records of what was installed** (`skills-lock.json`, `~/.agents/.skill-lock.json`). These exist because `npx` is imperative: something has to remember source, ref and hash so `install`, `update` and `check` work and teammates can restore. That's the npm `package-lock.json` role, and in a flake it's `flake.nix` (declares) plus `flake.lock` (pins). Vercel itself moved towards a declarative layer once one was available (`package.json` `skills` field, 2026-10-07).
- **Repo-specific configuration** (Matt Pocock's `docs/agents/*`, committed `.claude/settings.json` hooks or `enabledPlugins`). This is genuine: the tool can't know a repo's issue tracker or which hooks a team wants. In claws, `lib.project` in the repo's `flake.nix` is the place for that.

Reasons for a per-repo manifest, against a flake declaration:

- **Team sharing / restore on clone**: Yes: dev shell re-syncs hook files
- **Version pinning**: Yes: `flake.lock`
- **Update / uninstall tracking**: Yes: edit the declaration, `nix flake update`
- **Discoverability (what's on in this repo)**: Yes: it's in `flake.nix`
- **Using claws in a repo without touching its flake (someone else's repo, or no flake)**: No: this is the one thing `.claws.json` alone covers
- **Inline per-repo custom rules**: Only if `lib.project` takes them; Shane's setup excludes these anyway

## Gaps

- Claude Code docs pages carry no published date; treated as current as of the fetch on 2026-10-16.
- Didn't survey Codex's plugin/hook distribution separately (claws' ADR 0003 already covers why it's not used).
