# Host Adapter — DeepSeek Harness (DSH)

Load this only when the host is DeepSeek Harness (`@deepseek-ai/dsh`). Claude Code and Codex follow [`SKILL.md`](../SKILL.md) as written; this file records the four seams where DSH differs — invocation, approval, subagents (context, structured results, waves, staging), and sandbox/context — and what to do instead. It is a host adapter, not a second methodology — authoritative semantics still live in [`vibeloom-implementation.md`](../vibeloom-implementation.md) and [`vibeloom-methodology.md`](../vibeloom-methodology.md), and they win on any conflict.

---

## 1. Invocation

- Only a whitespace-bounded `/vibeloom` token triggers the skill. **`$vibeloom` does not exist in DSH** (the client's only gestures are `/` for commands/skills and `@` for references).
- Text after the token reaches the model verbatim; there is no `$ARGUMENTS` or positional substitution. Parse `operation` and `target` from the raw user message, then follow the routing table in [`SKILL.md`](../SKILL.md).
- `argument-hint` is inert: DSH tolerates unknown frontmatter keys but never reads them.

## 2. Approval gates

- Use `ask_user_question` (blocking by default): `questions[{id, question, header?, options[{label, description}], multi_select?}]` → `{answers:[{id, selected[], custom?}]}`. The call pauses the turn until a human answers.
- **Gate at the root agent.** A live subagent cannot ask — DSH rejects it with `DELEGATED_CALLER`. Subagents surface unresolved decisions in their final result; the orchestrator asks.
- `NO_PROVIDER`, `ASK_ABORTED`, and `DELEGATED_CALLER` all mean **not approved**. Never proceed and never fabricate consent from a failure.
- Gates that need this: `approve <tier>`, `reconcile` direction choices, breaking-change escalation, and any late-fetch request that would broaden a subagent's scope.

## 3. Target repo and sandbox

- Under `workspace-write` (the shipped default), writes are confined to the session workspace root plus `/tmp` — for the file tools **and** for any `python3`/bash child. The engine is a bash-invoked Python process and inherits the same fence.
- **The governed repository must be the session workspace.** Otherwise the user either grants `danger-full-access` for the session or runs the operation outside DSH. Do not promise governance of an arbitrary path.
- Subagents have approval pinned to `never`: they can never escalate, and approval-requiring work assigned to them is auto-rejected. Keep such work in the root agent.
- On `[sandbox: file access denied under workspace-write mode]`: **stop and report**. Do not retry with `sandbox_permissions` — a subagent's retry is auto-rejected, and a root retry requires explicit user consent.

## 4. Subagents

- A `subagent` child starts from an **empty conversation** and returns only its final text. Prompts must be self-contained: inline the task header and deliver the load set as explicit paths or inlined content.
- Use `subagent`. **Do not use `subagent_fork`** — fork seeds the child with the orchestrator's completed turns, which includes this skill's docs and the full planning context, violating the load-set discipline in [`runtime.md`](runtime.md).
- Children hold read/write/bash tools; write scope is enforced by the prompt, not by the host. Sibling writes must be disjoint by construction (wave assembly), because the host does not serialize them.
- Delegation depth is 1: children cannot delegate further.
- There is no per-child timeout. Enforce deadlines in the orchestrator.
- Respect the host's concurrency policy rather than a hardcoded number; the cap is a host setting.

## 5. Structured results

- The `subagent` tool has **no schema parameter**. On plain subagents the host cannot enforce `result_shape_id` or `summary.yaml`; treat the returned text as the summary and validate its required fields yourself.
- To get a validated object, use `workflow`'s `agent(prompt, {schema})`. Schemas are object-rooted and limited to `type` / `properties` / `required` / `additionalProperties` / `items` / `enum` / `const` / `oneOf`.
- Otherwise require children to emit a fenced JSON block matching the task template's `## Output` and parse it in the orchestrator.

## 6. Wave execution (replaces `execute_plan`)

- The engine CLI has no `execute` command: `execute_plan(plan, callback)` is a library API, and DSH's subagent is a model tool that a Python process cannot call back into. **The orchestrator drives the waves.**
- Recipe: run `dispatch` for the affected set → map the plan to `workflow` `args` with [`../dsh/dispatch-to-workflow.py`](../dsh/dispatch-to-workflow.py) → the script runs waves serially and scopes within a wave in parallel → sort accepted results by `scope_id` before landing, so the working tree is reproducible run-to-run (implementation §13.3).
- Same-wave outputs are not inputs to other same-wave tasks; cross-wave handoff happens only after a wave is accepted and the plan is recomputed.
- Full recipe, workflow script template, child prompt shape, and caps: [`../dsh/wave-runner.md`](../dsh/wave-runner.md).

## 7. Staging and landing

- DSH has no atomic multi-file commit primitive. Children write staging under `.vibeloom/runs/<RUN-ID>/tasks/<TASK-ID>/files/`; the orchestrator validates (summary → write scope → runners) and then lands.
- The host's changed-files summary does **not** record subagent sessions. Collect written paths from child results rather than relying on it.
- `write` refuses to overwrite a file the session has not read, `edit` requires a prior read, and observations do not survive a resume. Read a target artifact before regenerating it, or write through the engine.
- Step-by-step landing order (summary → write scope → staging → runners → land → trace) and the late-fetch rule: [`../dsh/wave-runner.md`](../dsh/wave-runner.md) §3.

## 8. Context artifacts

- DSH auto-loads `AGENTS.md` / `CLAUDE.md` from the project root down to the session cwd **only**. Root-level context artifacts are absorbed; a `CLAUDE.md` whose content duplicates its `AGENTS.md` is de-duplicated, so generate one, not two.
- Per-container and per-component `AGENTS.md` files are not in that chain. The owning subagent must read its scope config explicitly; a file created by bash or Python does not trigger discovery.
- Do not emit `context/AGENTS.md` — DSH does not load it.

## 9. What stays host-agnostic

Methodology, contract tiers, IDs, derivation rules, trace schemas, the verification ladder, task templates, and artifact templates are unchanged. Only the four seams above — invocation, approval, subagents, sandbox/context — differ by host. Install and troubleshooting for this host: [`../dsh/README.md`](../dsh/README.md); the underlying analysis is in [`../dsh-adaptation-report.md`](../dsh-adaptation-report.md).
