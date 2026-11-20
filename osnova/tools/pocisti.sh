#!/bin/sh
# Removes the worktrees whose work is on main (osnova: work.md): a worktree goes when it has no
# changes, not even an untracked file, and its branch's pull request was squash-merged with exactly the commit the
# worktree is on, more than ten minutes ago. Then nothing is lost: the work is a commit on main and the branch on
# GitHub is gone. The ten minutes leave the agent that merged time to finish, so an agent never removes its own
# worktree (Orca would stop its terminal); the next agent's run removes it. The main clone, the worktree this runs
# in, one with an open or unmerged pull request, or one left unmerged on purpose are never touched.
# What a project leaves behind outside git for a worktree (a test's containers, a cache) it removes itself, in
# tools/pocisti-projekat.sh: run last when there, with the same arguments, after the worktrees are gone.
#   sh tools/posalji.sh calls it after a merge; by hand: sh tools/pocisti.sh [--proba]   (--proba only lists)
set -eu
dry=0; [ "${1:-}" = --proba ] && dry=1
here=$(git rev-parse --show-toplevel)
own() {
  [ -f "$here/tools/pocisti-projekat.sh" ] || return 0
  sh "$here/tools/pocisti-projekat.sh" "$@" || echo "pocisti: tools/pocisti-projekat.sh nije uspeo." >&2
}
command -v orca >/dev/null 2>&1 || { echo "pocisti: nema orca; ništa nije uklonjeno."; own "$@"; exit 0; }
merged=$(gh pr list --state merged --limit 300 --json headRefName,headRefOid,mergedAt \
  --jq '.[] | select(now - (.mergedAt | fromdateiso8601) > 600) | "\(.headRefName) \(.headRefOid)"')
git worktree list --porcelain | sed -n 's/^worktree //p' | tail -n +2 | while read -r wt; do
  [ "$wt" = "$here" ] && continue
  [ -d "$wt" ] || continue
  [ -z "$(git -C "$wt" status --porcelain)" ] || continue
  branch=$(git -C "$wt" branch --show-current); head=$(git -C "$wt" rev-parse HEAD)
  [ -n "$branch" ] || continue
  printf '%s\n' "$merged" | grep -qx "$branch $head" || continue
  if [ "$dry" = 1 ]; then echo "pocisti: bi uklonio $wt ($branch)"; continue; fi
  if orca worktree rm --worktree "path:$wt" --delete-branch >/dev/null 2>&1; then
    echo "pocisti: uklonjen $wt ($branch)"
  else
    echo "pocisti: $wt nije uklonjen (orca worktree rm)." >&2
  fi
done
own "$@"
