# DSH wave runner (A5) + landing protocol (A6)

How the orchestrator drives VibeLoom's dispatch waves on DeepSeek Harness, and
how accepted results reach the working tree. Companion to
[`../references/host-dsh.md`](../references/host-dsh.md) §6–§7, which states the
constraints; this file is the executable recipe.

`execute_plan(plan, callback)` in [`../engine/vibeloom_engine/dispatch.py`](../engine/vibeloom_engine/dispatch.py)
is a library API that expects the host to return a subagent future. DSH exposes
subagents only as a model tool, so the orchestrator drives the waves and the
engine supplies the plan.

---

## 1. End-to-end recipe

### Step 1 — compute the plan (engine, deterministic)

```bash
PYTHONPATH=<skill-root>/engine python3 -m vibeloom_engine \
    --repo <repo> dispatch --ids <ID> [<ID> ...] --max-wave-size 5 \
    > .vibeloom/runs/<RUN-ID>/plan.json
```

`dispatch` emits `{plan_id, affected_set, waves[], max_wave_size}` where each
wave carries `wave_id`, `scopes[]` and `dependencies[]`. It makes no semantic
judgements; it assembles waves under implementation §13.2.

### Step 2 — convert to `workflow` args

```bash
python3 <skill-root>/dsh/dispatch-to-workflow.py \
    --plan .vibeloom/runs/<RUN-ID>/plan.json \
    --repo <repo> --skill-root <skill-root> --run-id <RUN-ID> \
    > .vibeloom/runs/<RUN-ID>/workflow-args.json
```

The converter re-checks the invariants that make parallel writes safe and fails
closed (exit 1) when the plan is unusable:

- a wave with no scopes, or a scope missing `scope_id` / `task_template_id`;
- a duplicate `scope_id` across waves;
- two scopes in one wave whose `owned_paths` overlap (prefix-aware, same
  normalization the engine uses).

`--repo` / `--skill-root` / `--run-id` are optional but recommended: children
need absolute paths to the repository, the skill root, and the run directory.

### Step 3 — run the waves

Call the `workflow` tool with `args` = the file from step 2 and `script` = the
template in §2. Waves run serially; scopes inside a wave run concurrently. The
parent turn sees one final JSON value, never intermediate child messages.

### Step 4 — land accepted results

Apply §4 in `scope_id` order, per wave, before assembling the next wave's load
sets.

---

## 2. Workflow script template

Plain JS body — no `export const meta`, top-level `await` allowed, ends with
`return <value>`. The VM exposes only `agent` / `pipeline` / `parallel` /
`phase` / `log` / `args`: no filesystem, no network, no timers. It therefore only
*builds prompts*; the children do the reading and writing.

```js
const SUMMARY_SCHEMA = {
  type: 'object',
  properties: {
    status: { enum: ['ok', 'partial', 'failed'] },
    patch_summary: { type: 'string' },
    files_written: { type: 'array', items: { type: 'string' } },
    files_read_outside: { type: 'array', items: { type: 'string' } },
    late_fetch_requested: { type: 'boolean' },
    validation_results: { type: 'object', additionalProperties: { type: 'string' } },
    decisions_emitted: { type: 'array', items: { type: 'string' } },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          severity: { type: 'string' },
          message: { type: 'string' },
          item_id: { type: 'string' }
        },
        required: ['severity', 'message'],
        additionalProperties: true
      }
    },
    notes: { type: 'string' }
  },
  required: ['status', 'patch_summary', 'files_written'],
  additionalProperties: true
}

function buildPrompt(scope, wave, args) {
  const stage = `${args.repo}/.vibeloom/runs/${args.run_id}/tasks/${scope.scope_id}`
  return [
    `# Subagent task: ${args.run_id}/${wave.wave_id}/${scope.scope_id}`,
    '',
    'You are a scoped VibeLoom subagent operating under a bounded contract.',
    `Repository root: ${args.repo}`,
    `Skill root: ${args.skill_root}`,
    '',
    '## Task header',
    '```yaml',
    `task_id: ${args.run_id}-${scope.scope_id}`,
    `run_id: ${args.run_id}`,
    `wave_id: ${wave.wave_id}`,
    `template_id: ${scope.task_template_id}`,
    `scope: ${scope.scope_id}`,
    `allowed_read_paths: ${JSON.stringify(scope.allowed_read_paths)}`,
    `allowed_write_paths: ${JSON.stringify(scope.owned_paths)}`,
    '```',
    '',
    'The header is binding. You inherit nothing from the orchestrator.',
    '',
    `1. Read \`${args.skill_root}/subagent-prompt.md\` for the contract shape.`,
    `2. Read \`${args.skill_root}/tasks/${scope.task_template_id}.md\` for your steps.`,
    '3. Read your load set from the repository; it is the authoritative scope.',
    `4. Stage writes under \`${stage}/files/\`; never write the working tree directly.`,
    `5. Read only within ${JSON.stringify(scope.allowed_read_paths)}; land only within ${JSON.stringify(scope.owned_paths)}.`,
    '6. Return the structured summary.',
    '',
    'Same-wave peers run concurrently: do not assume their output exists.'
  ].join('\n')
}

const byScopeId = (a, b) =>
  a.scope.scope_id < b.scope.scope_id ? -1 : a.scope.scope_id > b.scope.scope_id ? 1 : 0

const out = []
for (const wave of args.waves) {
  phase(wave.wave_id)
  log(`${wave.wave_id}: ${wave.scopes.length} scope(s), depends_on=${JSON.stringify(wave.depends_on || [])}`)

  const settled = await parallel(
    wave.scopes.map((scope) => async () =>
      agent(buildPrompt(scope, wave, args), {
        label: `${wave.wave_id}:${scope.scope_id}`,
        phase: wave.wave_id,
        schema: SUMMARY_SCHEMA
      })
    )
  )

  // Implementation §13.3: process results in deterministic scope_id order even
  // though they completed in arbitrary order.
  const ordered = wave.scopes
    .map((scope, i) => ({ scope, summary: settled[i] }))
    .sort(byScopeId)

  out.push({ wave_id: wave.wave_id, scopes: ordered })
}

return { plan_id: args.plan_id, run_id: args.run_id, waves: out }
```

Notes on the hooks:

- `agent(prompt, {schema})` resolves the **validated object**; without a schema it
  resolves the child's final text. A schema-requested call whose child produced no
  structured value resolves `null`, as does an ordinary child failure — treat
  `null` as a failed scope, never as success.
- `parallel(thunks)` is a barrier and returns `null` for a throwing thunk;
  `pipeline(items, ...stages)` has no barrier between stages and is the better
  choice if you ever chain per-scope stages.
- Schemas are object-rooted and limited to `type` / `properties` / `required` /
  `additionalProperties` / `items` / `enum` / `const` / `oneOf`.
- Use `subagent`-equivalent semantics: the workflow's `agent` spawns a fresh
  child. Do not reach for a fork-style primitive — it would seed the child with
  the orchestrator's context, including this skill's docs.

---

## 3. Landing protocol (A6)

For each wave, in `scope_id` order:

1. **Summary shape.** `null` → failed scope. Otherwise require `status`,
   `patch_summary`, `files_written`; a schema mismatch means the host did not
   enforce the contract, so validate explicitly.
2. **Write scope.** Every path in `files_written` must fall inside the scope's
   `owned_paths`. Anything else is a hard violation — fail the scope, keep the
   staging directory, and escalate.
3. **Staging present.** The staged files must exist under
   `.vibeloom/runs/<RUN-ID>/tasks/<scope_id>/files/`. A child that wrote the
   working tree directly is a protocol violation; do not land.
4. **Runners.** Run the `validation_contract` runners inside the staging
   directory (implementation §12 / the project's `validation-registry.md`).
   A blocking failure rejects the patch.
5. **Land.** On success, copy the staged files to their landing paths. DSH has no
   atomic multi-file commit, so land in the deterministic order above and record
   what landed. On failure, leave the staging directory in place for inspection —
   the working tree stays untouched.
6. **Trace.** Append the `generation` record (implementation §8.3), and for code
   scopes the `code-sync` record (§8.2), through the engine so the schema is
   enforced:

   ```bash
   PYTHONPATH=<skill-root>/engine python3 -c "
   from pathlib import Path
   from vibeloom_engine import traces
   traces.append_trace(Path('<repo>'), 'generations', { ... })
   "
   ```

   Trace appends are orchestrator-local. Children never write traces.

A failed scope does not block its same-wave peers: record the failure and
continue with the remaining scopes. Superseded accepted results are retired from
the active plan.

**Late-fetch.** A scope that reports `late_fetch_requested: true` gets **one**
re-invocation with the approved slice added to its prompt. On DSH that is simply
another `agent()` call — the child is fresh, so the whole prompt must be rebuilt
with the extra slice. A second request is a finding for human review, not another
attempt.

---

## 4. Caps and caveats

- **Do not hardcode concurrency.** The host's parallel-call and child limits are
  host settings; keep `max_wave_size` a policy value, not a constant tied to a
  number you observed once.
- **No per-child timeout.** Enforce deadlines in the orchestrator; a hung child
  will not be reaped by the host.
- **Keep everything inside the repository.** Under the default sandbox the bash
  `/tmp` is an ephemeral per-command tmpfs, so anything written there is gone by
  the next command. Plans, staging, and traces belong under `.vibeloom/runs/`.
- **The changed-files card ignores subagents.** Collect landed paths from the
  workflow's return value; do not rely on the session's change summary.
- **Approval-requiring work stays in the root agent.** Children cannot ask the
  user and cannot escalate the sandbox.

---

## 5. Verification

```bash
# converter compiles and rejects unsafe plans
python3 -m py_compile <skill-root>/dsh/dispatch-to-workflow.py
echo '{"waves":[]}' | python3 <skill-root>/dsh/dispatch-to-workflow.py   # exit 1

# end-to-end on a synthetic affected set
PYTHONPATH=<skill-root>/engine python3 -m vibeloom_engine --repo <repo> \
    dispatch --ids CMP-0001 CMP-0002 | python3 <skill-root>/dsh/dispatch-to-workflow.py --repo <repo> --skill-root <skill-root> --run-id RUN-TEST-0001
```

Acceptance: a three-scope affected set runs as one `workflow` call, returns
schema-validated summaries in `scope_id` order, and a deliberately failing scope
leaves its staging directory intact while its peers land.
