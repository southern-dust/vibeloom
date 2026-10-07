# `v03/dsh/` — DeepSeek Harness adapter (M0)

DSH-specific install and gate tooling for the VibeLoom v0.3 skill bundle. This
directory is additive: it does not change the skill surface, the methodology, or
the engine. The only change outside this directory is the quoted `description`
in the canonical template source ([`../vibeloom-templates.md`](../vibeloom-templates.md)),
which is required for DSH to load the skill at all.

Analysis and plan: [`../dsh-adaptation-report.md`](../dsh-adaptation-report.md) ·
[`../dsh-adaptation-plan.md`](../dsh-adaptation-plan.md).

## What M0 covers

| Item | Status |
|---|---|
| A1 — `SKILL.md` frontmatter is valid YAML (DSH drops the whole skill otherwise) | done |
| A1 — decidable frontmatter gate wired into the release build | done |
| A2 — install/uninstall entry point for DSH | done |
| A3 — DSH host adapter reference (`references/host-dsh.md`) | not yet (M1) |
| A4 — `subagent-prompt.md` path fix + DSH subagent notes | not yet (M1) |
| A5/A6 — `workflow`-based wave runner + staging convention | not yet (M2) |
| A7 — DSH context-artifact rules (`AGENTS.md` only at root) | not yet (M2) |

## Install

Run in a normal shell, **outside** the DSH sandbox. Under the default
`workspace-write` file policy a DSH agent cannot write to `~/.dsh` — the write is
denied, not a bug.

```bash
# user scope: $DSH_HOME/skills/vibeloom -> <repo>/v03
v03/dsh/install.sh

# project scope: <project>/.dsh/skills/vibeloom -> <repo>/v03
v03/dsh/install.sh --project /path/to/project

# preview, or remove
v03/dsh/install.sh --dry-run
v03/dsh/install.sh --uninstall
```

`--dsh-home DIR` overrides `$DSH_HOME` (default `~/.dsh`).

## Verify

```bash
# 1. frontmatter is loadable (the failure mode that made v0.3 invisible to DSH)
python3 v03/dsh/check-skill-frontmatter.py v03/SKILL.md

# 2. the bundle resolves as a skill
ls -l "${DSH_HOME:-$HOME/.dsh}/skills/vibeloom/SKILL.md"
```

Then in a DSH session the catalog should list `vibeloom`, and the `/vibeloom`
gesture should inject the skill body:

```
/vibeloom status
```

## Why a symlink and not `customSkillDirs`

DSH discovers skills as `<root>/<name>/SKILL.md` or `<root>/<name>.md`, exactly
one level deep, and takes the name from the frontmatter. **Do not** point
`customSkillDirs` at the repository root: `v01/`, `v02/`, and `v03/` all declare
`name: vibeloom`, and same-layer duplicate resolution is first-wins by directory
order — the archived `v01` skill would shadow v03. Point it at a directory that
contains only the v03 bundle, or use this installer.

## DSH facts the skill surface has to respect (M1/M2 input)

These are recorded here because M0 only fixes loadability; the skill text still
assumes Claude Code / Codex in several places.

- **Invocation.** Only a whitespace-bounded `/vibeloom` token works. `$vibeloom`
  does not exist in DSH (the client's only gestures are `/` and `@`). Text after
  the token reaches the model verbatim; there is no `$ARGUMENTS` substitution, so
  the operation and target are parsed from the raw message.
- **`argument-hint` is inert.** DSH tolerates unknown frontmatter keys but never
  reads them.
- **Approval gates.** Use `ask_user_question` (blocking by default). A live
  subagent cannot ask (`DELEGATED_CALLER`); gates belong to the root agent.
  `NO_PROVIDER`, `ASK_ABORTED`, and `DELEGATED_CALLER` all mean *not approved*.
- **Sandbox.** `workspace-write` confines writes to the session workspace root
  plus `/tmp`, for the file tools **and** for any `python3`/bash child. The
  governed repository must be the session workspace, or the user must grant
  `danger-full-access`. Subagents have approval pinned to `never` and can never
  escalate.
- **Subagents.** `subagent` children start with an empty conversation and return
  only final text; there is no schema parameter. Prompts must be self-contained.
  Use `subagent`, not `subagent_fork` — fork would leak the orchestrator's
  context (including this skill's docs) into the child, against the load-set
  discipline in `references/runtime.md`.
- **Structured results.** `workflow`'s `agent(prompt, {schema})` is the only
  model-reachable way to get a validated object; schemas are object-rooted and
  limited to `type`/`properties`/`required`/`additionalProperties`/`items`/`enum`/
  `const`/`oneOf`.
- **Context artifacts.** DSH auto-loads `AGENTS.md` / `CLAUDE.md` from the
  project root down to the session cwd only. Per-container/per-component
  `AGENTS.md` files are not in that chain and must be read explicitly by the
  subagent that owns the scope. A `CLAUDE.md` whose content duplicates its
  `AGENTS.md` is de-duplicated.
- **Volatile caps.** `maxParallelToolCalls` (default 10), `subagent.maxDepth`
  (default 1), and `maxActiveSubagents` (default 8) are host settings. Do not
  hardcode them in skill semantics.
