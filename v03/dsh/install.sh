#!/usr/bin/env bash
#
# install.sh — install the VibeLoom v0.3 skill bundle into DeepSeek Harness (DSH).
#
# DSH discovers a skill as `<root>/<name>/SKILL.md` or `<root>/<name>.md`, exactly
# one level deep, and takes the skill name from the frontmatter. The v03 bundle
# therefore has to be reachable as a directory named `vibeloom` whose SKILL.md is
# this version's SKILL.md — a symlink is the cheapest correct way to do that.
#
#   user scope (default):  $DSH_HOME/skills/vibeloom        -> <repo>/v03
#   project scope:         <project>/.dsh/skills/vibeloom   -> <repo>/v03
#
# DO NOT point DSH's `customSkillDirs` at the repository root (or any directory
# that also contains v01/ and v02/): all three declare `name: vibeloom`, and
# same-layer duplicate resolution is first-wins by directory order, so the
# archived v01 skill would shadow v03. Use this script, or a directory that
# contains only the v03 bundle.
#
# NOTE: writing to $DSH_HOME (or a project `.dsh/`) is outside the DSH file
# sandbox. Under the default `workspace-write` policy a DSH agent cannot run
# this script; the user runs it in a normal shell.
#
set -euo pipefail

SKILL_NAME="vibeloom"
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # -> v03/
DSH_HOME="${DSH_HOME:-$HOME/.dsh}"
SCOPE="user"
PROJECT_DIR=""
UNINSTALL=0
DRY_RUN=0
FORCE=0

usage() {
  cat <<'EOF'
Install the VibeLoom v0.3 skill into DeepSeek Harness.

Usage:
  ./install.sh [--user | --project [DIR]] [--dsh-home DIR] [--dry-run] [--force]
  ./install.sh --uninstall [--user | --project [DIR]] [--dsh-home DIR] [--dry-run] [--force]

Options:
  --user              Install into $DSH_HOME/skills/vibeloom (default).
  --project [DIR]     Install into DIR/.dsh/skills/vibeloom (DIR defaults to $PWD).
  --dsh-home DIR      DSH home for --user (default: $DSH_HOME or ~/.dsh).
  --uninstall         Remove the symlink this script created.
  --dry-run           Print what would happen; change nothing.
  --force             Replace an existing symlink that points elsewhere.
  -h, --help          Show this help.

Exit codes: 0 success, 1 refused/failed, 2 bad invocation.
EOF
}

die() { echo "ERROR: $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --user) SCOPE="user"; shift ;;
    --project)
      SCOPE="project"; shift
      if [ $# -gt 0 ] && [ "${1#--}" = "$1" ]; then PROJECT_DIR="$1"; shift; fi
      ;;
    --dsh-home) [ $# -ge 2 ] || die "--dsh-home needs a directory"; DSH_HOME="$2"; shift 2 ;;
    --uninstall) UNINSTALL=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; die "unknown argument: $1" ;;
  esac
done

[ -f "$SOURCE/SKILL.md" ] || die "SKILL.md not found at $SOURCE — run extract-templates.py first"

if [ "$SCOPE" = "user" ]; then
  TARGET="$DSH_HOME/skills/$SKILL_NAME"
else
  PROJECT_DIR="${PROJECT_DIR:-$PWD}"
  [ -d "$PROJECT_DIR" ] || die "project directory does not exist: $PROJECT_DIR"
  PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"
  TARGET="$PROJECT_DIR/.dsh/skills/$SKILL_NAME"
fi

echo "skill source : $SOURCE"
echo "install target: $TARGET"
echo "scope        : $SCOPE"
[ "$DRY_RUN" = "1" ] && echo "mode         : dry-run"

# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------
if [ "$UNINSTALL" = "1" ]; then
  if [ ! -e "$TARGET" ] && [ ! -L "$TARGET" ]; then
    echo "nothing to do: $TARGET does not exist"
    exit 0
  fi
  if [ ! -L "$TARGET" ]; then
    die "$TARGET is a real directory, not a symlink; refusing to delete it. Remove it manually if that is intended."
  fi
  CURRENT="$(readlink -f "$TARGET" || true)"
  if [ "$CURRENT" != "$SOURCE" ] && [ "$FORCE" != "1" ]; then
    die "$TARGET points to '$CURRENT', not '$SOURCE'; pass --force to remove it anyway."
  fi
  if [ "$DRY_RUN" = "1" ]; then
    echo "would remove symlink: $TARGET"
    exit 0
  fi
  rm "$TARGET"
  echo "removed symlink: $TARGET"
  exit 0
fi

# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------
if [ -L "$TARGET" ]; then
  CURRENT="$(readlink -f "$TARGET" || true)"
  if [ "$CURRENT" = "$SOURCE" ]; then
    echo "already installed: $TARGET -> $SOURCE"
    exit 0
  fi
  if [ "$FORCE" != "1" ]; then
    die "$TARGET already exists and points to '$CURRENT'; pass --force to repoint it."
  fi
  [ "$DRY_RUN" = "1" ] || rm "$TARGET"
elif [ -e "$TARGET" ]; then
  die "$TARGET exists and is not a symlink; refusing to replace it. Move it aside first."
fi

if [ "$DRY_RUN" = "1" ]; then
  echo "would create: $TARGET -> $SOURCE"
  exit 0
fi

mkdir -p "$(dirname "$TARGET")"
ln -sfn "$SOURCE" "$TARGET"
echo "installed: $TARGET -> $SOURCE"

cat <<EOF

Next steps (in a DSH session):
  1. The skill catalog should now list \`$SKILL_NAME\`. If it does not, check
     that SKILL.md frontmatter is valid:
         python3 "$SOURCE/dsh/check-skill-frontmatter.py" "$SOURCE/SKILL.md"
  2. Invoke it with the /$SKILL_NAME gesture (there is no \$$SKILL_NAME form):
         /$SKILL_NAME status
  3. Keep the governed repository inside the DSH session workspace. Under the
     default workspace-write sandbox, writes outside the session workspace are
     denied for the file tools and for any python3/bash child.

Uninstall with: $0 --uninstall$( [ "$SCOPE" = project ] && printf ' --project %s' "$PROJECT_DIR" )
EOF
