#!/usr/bin/env bash
# Build the git commit history for the anvil-chatkit repo.
#
# Usage:
#   1. cd into the anvil_chatkit/ directory (this script's directory)
#   2. git init -b main && git config user.name "..." && git config user.email "..."
#   3. bash setup-history.sh
#   4. git remote add origin git@github.com:anvil-industries/anvil-chatkit.git
#   5. git push -u origin main
#
# This creates 6 commits, one of which (commit #4) carries flag #15 in its
# message. Players who run `git log` on the public repo will find it.

set -euo pipefail

if [ ! -d .git ]; then
  echo "ERROR: run this from a directory that has been 'git init'-ed already." >&2
  exit 1
fi

# 1. Scaffold + license
git add LICENSE pyproject.toml .gitignore
git commit -m "Initial commit: project scaffolding and license"

# 2. Persona dataclass + package init
git add src/anvil_chatkit/__init__.py
git commit -m "Add Persona dataclass and package init"

# 3. ChatKit wrapper class
git add src/anvil_chatkit/app.py
git commit -m "Add ChatKit FastAPI wrapper class"

# 4. Empty commit — carries flag #15 in the message
git commit --allow-empty \
  -m "Internal note: rolled back experimental auth helper. Audit canary: flag{ancient_typewriter}"

# 5. Tests
git add tests/
git commit -m "Add unit tests for ChatKit"

# 6. README — also bumps the version reference
git add README.md
git commit -m "Document API in README and link demo Gist"

echo
echo "Done. Six commits made. Push with:"
echo "  git remote add origin git@github.com:anvil-industries/anvil-chatkit.git"
echo "  git push -u origin main"
