#!/bin/sh
# A task's branch to main (AGENTS.md, "How to work here"), in one go and in the right order: rebase on origin/main,
# the tests, push, the pull request (opened with the body in <file> unless it is open already), then wait until the
# **test** check has started and passed, and squash-merge. A check that has not started yet is not "passed": on
# 20 Nov 2026 a pull request was merged before its test began.
#   sh tools/posalji.sh [<file with the PR body>] [--ne-spajaj]
# --ne-spajaj stops after the check, for a pull request the maintainer merges (a principle, DNS, what is seen outside).
set -eu
body=""; merge=1
for a in "$@"; do
  case "$a" in
    --ne-spajaj) merge=0 ;;
    *) body="$a" ;;
  esac
done
branch=$(git rev-parse --abbrev-ref HEAD)
[ "$branch" = main ] && { echo "posalji: na main-u si; grana pa PR (AGENTS.md)." >&2; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "posalji: ima izmena koje nisu commit-ovane." >&2; git status --short >&2; exit 1; }

git fetch -q origin
git rebase -q origin/main
uv run pytest -q
git push -q --force-with-lease -u origin HEAD

if ! gh pr view --json number >/dev/null 2>&1; then
  [ -n "$body" ] && [ -f "$body" ] || { echo "posalji: PR još ne postoji; daj fajl sa opisom (šablon: šta, zašto, provereno, odluka)." >&2; exit 1; }
  gh pr create --fill-first --body-file "$body"
fi
pr=$(gh pr view --json number -q .number)

echo "posalji: čekam da check test krene na #$pr…"
i=0
until gh pr checks "$pr" 2>/dev/null | grep -q '^test[[:space:]]'; do
  i=$((i + 1)); [ "$i" -gt 60 ] && { echo "posalji: test nije krenuo za 5 minuta." >&2; exit 1; }
  sleep 5
done
gh pr checks "$pr" --watch --fail-fast
gh pr checks "$pr" | grep -q '^test[[:space:]]*pass' || { echo "posalji: test nije prošao na #$pr." >&2; exit 1; }

if [ "$merge" = 1 ]; then
  gh pr merge "$pr" --squash --delete-branch || gh pr view "$pr" --json state -q .state | grep -q MERGED
  echo "posalji: #$pr je spojen."
else
  echo "posalji: #$pr čeka održavaoca."
fi
