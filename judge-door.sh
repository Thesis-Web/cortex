#!/bin/bash
# judge-door.sh (2026-11-06): the edge, one sql statement to the kernel's door and its answer; no logic here. usage: judge-door.sh <port> "<sql on one line>"
exec 3<>/dev/tcp/127.0.0.1/${1:-7010} || exit 1
printf 'q %s\n' "$2" >&3
timeout ${3:-120} head -n 1 <&3
exec 3>&-
