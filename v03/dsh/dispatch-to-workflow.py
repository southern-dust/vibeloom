#!/usr/bin/env python3
"""
dispatch-to-workflow.py — turn an engine dispatch plan into `workflow` tool args.

Why this exists
---------------
VibeLoom's parallel semantics live in `execute_plan(plan, callback)`, a library
API that expects the host to hand back a real subagent future. DeepSeek Harness
exposes subagents only as a *model* tool, so a Python process cannot call back
into it. The orchestrator therefore drives the waves, and the bridge is:

    engine dispatch  ->  this script  ->  workflow(meta, args)  ->  agent(prompt, {schema})

This script is the middle step: it reads the plan JSON the engine emits, checks
the wave invariants that make parallel writes safe, and emits the `args` object
the workflow script consumes.

Usage
-----
    PYTHONPATH=<skill-root>/engine python3 -m vibeloom_engine --repo <repo> \\
        dispatch --ids <ID> [<ID> ...] --max-wave-size 5 \\
      | python3 <skill-root>/dsh/dispatch-to-workflow.py \\
          --repo <repo> --skill-root <skill-root> --run-id RUN-YYYYMMDD-NNNN

    # or from a saved plan
    python3 dispatch-to-workflow.py --plan plan.json --repo ... --skill-root ...

Exit codes: 0 = ok, 1 = invalid plan, 2 = bad invocation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_SCOPE_FIELDS = ("scope_id", "task_template_id")


def _normalize(path: str) -> str:
    """Same prefix semantics the engine uses: `web/src/**` -> `web/src/`."""
    return path.split("**", 1)[0]


def _overlaps(a: list[str], b: list[str]) -> tuple[str, str] | None:
    for pa in (_normalize(p) for p in a):
        for pb in (_normalize(p) for p in b):
            if not pa or not pb:
                continue
            if pa == pb or pa.startswith(pb) or pb.startswith(pa):
                return pa, pb
    return None


def convert(plan: object) -> tuple[dict | None, list[str]]:
    errors: list[str] = []
    if not isinstance(plan, dict):
        return None, [f"plan must be a JSON object (got {type(plan).__name__})"]

    waves_in = plan.get("waves")
    if not isinstance(waves_in, list) or not waves_in:
        return None, ["plan has no `waves` list (nothing to dispatch)"]

    waves_out = []
    seen_scopes: set[str] = set()
    for i, wave in enumerate(waves_in):
        if not isinstance(wave, dict):
            errors.append(f"waves[{i}] is not an object")
            continue
        wave_id = wave.get("wave_id") or f"W{i + 1}"
        scopes_in = wave.get("scopes")
        if not isinstance(scopes_in, list) or not scopes_in:
            errors.append(f"{wave_id}: no scopes")
            continue

        scopes_out = []
        for j, scope in enumerate(scopes_in):
            if not isinstance(scope, dict):
                errors.append(f"{wave_id}.scopes[{j}] is not an object")
                continue
            missing = [f for f in REQUIRED_SCOPE_FIELDS if not scope.get(f)]
            if missing:
                errors.append(f"{wave_id}.scopes[{j}]: missing {', '.join(missing)}")
                continue
            sid = scope["scope_id"]
            if sid in seen_scopes:
                errors.append(f"duplicate scope_id {sid!r} across waves")
            seen_scopes.add(sid)
            scopes_out.append(
                {
                    "scope_id": sid,
                    "kind": scope.get("kind", ""),
                    "task_template_id": scope["task_template_id"],
                    "owned_paths": list(scope.get("owned_paths") or []),
                    "allowed_read_paths": list(scope.get("allowed_read_paths") or []),
                    "is_reconciliation": bool(scope.get("is_reconciliation", False)),
                    "is_eval": bool(scope.get("is_eval", False)),
                }
            )

        # Wave-assembly rule 1 (impl §13.2): same-wave ownership must be disjoint.
        for a in range(len(scopes_out)):
            for b in range(a + 1, len(scopes_out)):
                hit = _overlaps(scopes_out[a]["owned_paths"], scopes_out[b]["owned_paths"])
                if hit:
                    errors.append(
                        f"{wave_id}: scopes {scopes_out[a]['scope_id']!r} and "
                        f"{scopes_out[b]['scope_id']!r} overlap on {hit[0]!r} / {hit[1]!r} "
                        f"— parallel writes would collide"
                    )

        waves_out.append(
            {
                "wave_id": wave_id,
                "depends_on": [d.get("from") for d in (wave.get("dependencies") or []) if isinstance(d, dict) and d.get("from")],
                "scopes": scopes_out,
            }
        )

    if errors:
        return None, errors

    out: dict = {
        "plan_id": plan.get("plan_id", ""),
        "max_wave_size": plan.get("max_wave_size"),
        "affected_set": list(plan.get("affected_set") or []),
        "waves": waves_out,
    }
    return out, []


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Convert an engine dispatch plan into workflow `args`.")
    ap.add_argument("--plan", help="plan JSON file (default: read stdin)")
    ap.add_argument("--repo", help="absolute path to the governed repository (added to args)")
    ap.add_argument("--skill-root", help="absolute path to the VibeLoom skill root (added to args)")
    ap.add_argument("--run-id", help="run id for this dispatch (added to args)")
    ap.add_argument("--compact", action="store_true", help="emit single-line JSON")
    args = ap.parse_args(argv)

    try:
        raw = Path(args.plan).read_text(encoding="utf-8") if args.plan else sys.stdin.read()
    except OSError as exc:
        print(f"ERROR: cannot read plan: {exc}", file=sys.stderr)
        return 2

    if not raw.strip():
        print("ERROR: empty plan input", file=sys.stderr)
        return 2

    try:
        plan = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"ERROR: plan is not valid JSON: {exc}", file=sys.stderr)
        return 2

    converted, errors = convert(plan)
    if converted is None:
        print("FAIL: plan rejected", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    out: dict = {}
    if args.repo:
        out["repo"] = str(Path(args.repo).resolve())
    if args.skill_root:
        out["skill_root"] = str(Path(args.skill_root).resolve())
    if args.run_id:
        out["run_id"] = args.run_id
    out.update(converted)

    json.dump(out, sys.stdout, indent=None if args.compact else 2, sort_keys=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
