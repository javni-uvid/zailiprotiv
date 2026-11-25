#!/bin/sh
# What a workflow read or wrote, to the branch it runs on: commits what is staged and sends every commit the branch
# on the server lacks. Ends with 0 only when the server's branch has them (asked of the server after the push), or
# when there was nothing to send; otherwise with 1, so that a run which lost its commit is red. On 24 Nov 2026 an
# hour's reading was lost in a green run: the rebase met a conflict, and `git status -sb` in an unfinished rebase
# has no "ahead" to show.
#   sh tools/predaj.sh ["<commit message>"]
# With no message only the commits already made are sent. Changes not staged stay as they are (`git pull --rebase`
# refuses beside them). PREDAJ_REMOTE: the remote or its address (origin), for a checkout that keeps no token.
# PREDAJ_TRIES, PREDAJ_SLEEP: how many tries (5) and the seconds between them (5). Nothing here is of one project:
# POSIX sh and git, run anywhere in it.
main() {
  remote=${PREDAJ_REMOTE:-origin}
  branch=$(git symbolic-ref -q --short HEAD) || { echo "::error::predaj: no branch is checked out, or a rebase is unfinished."; return 1; }
  if [ -z "$(git config user.email || true)" ]; then
    git config user.name "github-actions[bot]"
    git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  fi
  if [ -n "${1:-}" ] && ! git diff --cached --quiet; then git commit -q -m "$1" || return 1; fi
  try=0
  while [ "$try" -lt "${PREDAJ_TRIES:-5}" ]; do
    [ "$try" -eq 0 ] || sleep "${PREDAJ_SLEEP:-5}"
    try=$((try + 1))
    git fetch -q "$remote" "refs/heads/$branch" || continue
    if git merge-base --is-ancestor HEAD FETCH_HEAD; then return 0; fi  # there already, or nothing to send
    if ! git rebase -q --autostash FETCH_HEAD; then
      echo "predaj: the rebase stopped at: $(git diff --name-only --diff-filter=U | tr '\n' ' ')"
      git rebase --abort 2>/dev/null || git rebase --quit 2>/dev/null || true
      continue
    fi
    git push -q "$remote" "HEAD:refs/heads/$branch" || continue
    # Said by the server, not by the push or by what the checkout believes.
    if git fetch -q "$remote" "refs/heads/$branch" && git merge-base --is-ancestor HEAD FETCH_HEAD; then
      echo "predaj: $(git rev-parse --short HEAD) is on $branch."
      return 0
    fi
  done
  echo "::error::predaj: NOT on $branch, and lost with this run: $(git log -1 --format='%h %s')"
  return 1
}
main "$@"
exit $?
