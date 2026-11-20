#!/bin/sh
# What this project leaves in Docker for a worktree, removed once the worktree is gone (osnova/tools/pocisti.sh runs
# this last; `mikrofon.ps1 ocisti` too). A worktree's test of the live service (`mikrofon.ps1 test`) is a compose
# stack of its own, mikrofon-test-<branch>: a running container of about 1 GB of memory, an image of 1.8 GB and a
# volume. Whatever in Docker carries that name for a branch no worktree is on any more goes: containers, the image,
# the volume, the network. The main clone's own test (mikrofon-test, mikrofon:test), the live service and whatever
# is named otherwise are never touched.
#   sh tools/pocisti-projekat.sh [--proba]   (--proba only lists)
set -eu
dry=0; [ "${1:-}" = --proba ] && dry=1
command -v docker >/dev/null 2>&1 || exit 0
docker info >/dev/null 2>&1 || exit 0      # Docker isn't running: nothing to stop, and what stays goes next time

# The name mikrofon.ps1 gives a branch's test: the last part of the branch, lower case, anything else a dash, 30 long.
slug() {
  printf '%s' "${1##*/}" | tr 'A-Z' 'a-z' | sed 's/[^a-z0-9-]/-/g; s/^-*//; s/-*$//' | cut -c1-30 | sed 's/-*$//'
}
kept=" "
for b in $(git worktree list --porcelain | sed -n 's|^branch refs/heads/||p'); do kept="$kept$(slug "$b") "; done

gone() { case "$kept" in *" $1 "*) return 1 ;; esac; [ -n "$1" ]; }
say() { if [ "$dry" = 1 ]; then echo "pocisti: bi uklonio $1"; else echo "pocisti: uklonjen $1"; fi; }

docker ps -a --format '{{.Label "com.docker.compose.project"}}' | sort -u | sed -n 's/^mikrofon-test-//p' |
while read -r s; do
  gone "$s" || continue
  say "test mikrofon-test-$s (kontejneri)"
  [ "$dry" = 1 ] && continue
  l="label=com.docker.compose.project=mikrofon-test-$s"      # by the label: no compose file is left to read
  docker ps -aq --filter "$l" | xargs -r docker rm -f >/dev/null 2>&1 || true
  docker network ls -q --filter "$l" | xargs -r docker network rm >/dev/null 2>&1 || true
done
docker images mikrofon --format '{{.Tag}}' | sed -n 's/^test-//p' |
while read -r s; do
  gone "$s" || continue
  say "image mikrofon:test-$s"
  [ "$dry" = 1 ] || docker rmi "mikrofon:test-$s" >/dev/null 2>&1 || true
done
docker volume ls --format '{{.Name}}' | sed -n 's/^mikrofon-test-\(.*\)-podaci$/\1/p' |
while read -r s; do
  gone "$s" || continue
  say "volumen mikrofon-test-$s-podaci"
  [ "$dry" = 1 ] || docker volume rm "mikrofon-test-$s-podaci" >/dev/null 2>&1 || true
done
