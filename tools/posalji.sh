#!/bin/sh
# The organization's script (osnova/tools/, brought by the osnova workflow) does the work.
exec sh "$(git rev-parse --show-toplevel)/osnova/tools/posalji.sh" "$@"
