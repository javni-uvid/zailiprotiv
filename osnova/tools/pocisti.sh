#!/bin/sh
# Removes the worktrees whose work is on main (osnova: work.md): a worktree goes when it has no
# changes, not even an untracked file, and its branch's pull request was squash-merged with exactly the commit the
# worktree is on, more than ten minutes ago. Then nothing is lost: the work is a commit on main and the branch on
# GitHub is gone. The main clone, the worktree this runs in, one with an open or unmerged pull request, or one left
# unmerged on purpose are never touched, and neither is:
# - one an agent is in (agenti.py, just before each removal): on 25 Nov 2026 two sessions at work were stopped, as
#   only git's state was looked at. Orca is asked, so nobody has to set or take off anything; when it can't be
#   asked, nothing is removed.
# - one locked in git (`git worktree lock --reason <why> <path>`), for what Orca doesn't see: an agent outside its
#   terminals, a folder to be kept. Whoever locks it unlocks it.
# Each that stays only for one of these two is named, with the reason.
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
locked=$(git worktree list --porcelain | awk '/^worktree /{p=substr($0,10)} /^locked/{print p}')
said=$(mktemp -d); trap 'rm -rf "$said"' EXIT
# Why a worktree stays though its work is on main; nothing when it may go.
stays() {
  printf '%s
' "$locked" | grep -qxF "$1" && { echo "zaključan je (git worktree unlock)"; return; }
  command -v uv >/dev/null 2>&1 || { echo "nema uv, pa ne znam ko u njemu radi"; return; }
  orca worktree ps --limit 1000 --json </dev/null >"$said/ps" 2>/dev/null || { echo "Orca se ne javlja"; return; }
  orca terminal list --limit 1000 --json </dev/null >"$said/t" 2>/dev/null || { echo "Orca se ne javlja"; return; }
  why=$(uv run -q --no-project "$(dirname "$0")/agenti.py" "$1" "$said/ps" "$said/t" </dev/null 2>/dev/null) && return
  echo "${why:-ne znam ko u njemu radi}"
}
git worktree list --porcelain | sed -n 's/^worktree //p' | tail -n +2 | while read -r wt; do
  [ "$wt" = "$here" ] && continue
  [ -d "$wt" ] || continue
  [ -z "$(git -C "$wt" status --porcelain)" ] || continue
  branch=$(git -C "$wt" branch --show-current); head=$(git -C "$wt" rev-parse HEAD)
  [ -n "$branch" ] || continue
  printf '%s\n' "$merged" | grep -qx "$branch $head" || continue
  why=$(stays "$wt")
  if [ -n "$why" ]; then echo "pocisti: ostaje $wt ($branch): $why"; continue; fi
  if [ "$dry" = 1 ]; then echo "pocisti: bi uklonio $wt ($branch)"; continue; fi
  if orca worktree rm --worktree "path:$wt" --delete-branch </dev/null >/dev/null 2>&1; then
    echo "pocisti: uklonjen $wt ($branch)"
  else
    echo "pocisti: $wt nije uklonjen (orca worktree rm)." >&2
  fi
done
own "$@"
