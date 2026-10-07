#!/usr/bin/env python3
"""
check-skill-frontmatter.py — decidable frontmatter gate for host skill loaders.

Why this exists
---------------
DeepSeek Harness (DSH) parses a skill's YAML frontmatter with a strict YAML
loader and, on any parse error, logs a warning and drops the *whole* skill with
no per-skill diagnostic. The model catalog then simply does not contain it.
v03.0 shipped exactly this bug: an unquoted `description` containing
`(modes: vibe, ...)` is not a valid plain scalar (`": "` starts a mapping), so
the skill was invisible to DSH.

This gate makes that failure loud at build time instead of silent at load time.
It checks the frontmatter the way a strict loader plus the loader's own
name/description rules would:

  * the first line is exactly `---` and a closing `---` exists
  * top-level keys are unique (the npm `yaml` loader used by DSH rejects
    duplicates; PyYAML's safe_load does not, so this is checked structurally)
  * no unquoted plain scalar contains `": "` or starts with a YAML indicator
  * `name` is a non-empty kebab-case string (`^[a-z0-9]+(?:-[a-z0-9]+)*$`)
  * `description` is a non-empty string (not parsed as a number/boolean)

Unknown keys (e.g. `argument-hint`, `allowed-tools`) are tolerated on purpose:
DSH ignores keys it does not know, and rejecting them here would be stricter
than the host.

Usage
-----
    python3 check-skill-frontmatter.py [path/to/SKILL.md]

The default target is the `SKILL.md` next to this script's parent directory
(`v03/SKILL.md` when the script lives in `v03/dsh/`).

Exit codes: 0 = valid, 1 = invalid, 2 = bad invocation.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# DSH: /^[a-z0-9]+(?:-[a-z0-9]+)*$/ (dsh-skill/lib/index.js)
SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Characters that cannot start a YAML plain scalar.
INDICATORS = "-?:,[]{}#&*!|>'\"%@`"

KEY_LINE = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_.-]*):(.*)$")


def split_frontmatter(text: str) -> tuple[str | None, str]:
    """Return (frontmatter, error). The first line must be exactly `---`."""
    lines = text.splitlines()
    if not lines or lines[0].rstrip("\r") != "---":
        return None, "first line is not exactly `---` (a leading blank line or BOM defeats discovery)"
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r") == "---":
            return "\n".join(lines[1:i]), ""
    return None, "no closing `---` line found"


def structural_checks(fm: str) -> list[str]:
    """Checks that do not need a YAML library (duplicates, plain-scalar hazards)."""
    errors: list[str] = []
    seen: dict[str, int] = {}
    for n, line in enumerate(fm.splitlines(), start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1] in (" ", "\t", "-"):
            continue  # nested/sequence content: out of scope for the flat skill header
        m = KEY_LINE.match(line)
        if not m:
            errors.append(f"line {n}: not a top-level `key: value` line: {line!r}")
            continue
        key, raw = m.group(1), m.group(2)
        if key in seen:
            errors.append(f"line {n}: duplicate frontmatter key {key!r} (first at line {seen[key]})")
        seen[key] = n
        value = raw.strip()
        if value == "":
            continue  # emptiness of name/description is reported by the semantic check
        quoted = value[0] in ("'", '"')
        if quoted:
            continue
        if ": " in value:
            errors.append(
                f"line {n}: unquoted {key!r} value contains ': ' — not a valid YAML plain scalar; "
                f"quote the value (this is the v03.0 SKILL.md bug)"
            )
        if value[0] in INDICATORS:
            errors.append(f"line {n}: unquoted {key!r} value starts with YAML indicator {value[0]!r}; quote it")
    return errors


def semantic_checks(data: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return [f"frontmatter is not a YAML mapping (got {type(data).__name__})"]
    name = data.get("name")
    desc = data.get("description")
    if not isinstance(name, str) or not name:
        errors.append(f"`name` must be a non-empty string (got {name!r})")
    elif not SKILL_NAME.match(name):
        errors.append(f"`name` must be kebab-case matching ^[a-z0-9]+(-[a-z0-9]+)*$ (got {name!r})")
    if not isinstance(desc, str) or not desc:
        errors.append(f"`description` must be a non-empty string (got {desc!r}); quote it if YAML reads it as a number/bool")
    return errors


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Decidable SKILL.md frontmatter gate.")
    ap.add_argument("target", nargs="?", default=None, help="path to SKILL.md (default: ../SKILL.md)")
    ap.add_argument("--quiet", action="store_true", help="only report failures")
    args = ap.parse_args(argv)

    target = Path(args.target) if args.target else Path(__file__).resolve().parent.parent / "SKILL.md"
    if not target.is_file():
        print(f"ERROR: {target} not found", file=sys.stderr)
        return 2

    fm, err = split_frontmatter(target.read_text(encoding="utf-8"))
    if fm is None:
        print(f"FAIL: {target}: {err}", file=sys.stderr)
        return 1

    errors = structural_checks(fm)

    mode = "structural only (PyYAML not importable)"
    try:
        import yaml  # type: ignore

        mode = f"strict YAML (PyYAML {yaml.__version__}) + structural"
        try:
            errors += semantic_checks(yaml.safe_load(fm))
        except Exception as exc:  # noqa: BLE001 - any parse error is fatal to the loader
            errors.append(f"YAML parse error: {exc}")
    except ImportError:
        # Fall back to structural-only name/description checks.
        fields = {}
        for line in fm.splitlines():
            m = KEY_LINE.match(line)
            if m:
                fields.setdefault(m.group(1), m.group(2).strip())
        errors += semantic_checks({k: v.strip("'\"") for k, v in fields.items()})

    if errors:
        print(f"FAIL: {target} [{mode}]", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"OK: {target} frontmatter valid [{mode}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
