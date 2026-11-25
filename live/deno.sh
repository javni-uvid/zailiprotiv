#!/bin/sh
# Deno as yt-dlp finds it, under a time limit: yt-dlp gives it none, and one that hung would hold the loop (cuvar.py). A
# script of YouTube's takes it a second. Ended, yt-dlp goes on without what it would have worked out.
exec timeout -k 5 30 /usr/local/lib/deno/deno "$@"
