#!/bin/bash
# start-nk.sh (C54, 2026-11-04): the cortex kernel started with the source list in sources/LIST (the attached dbs; sqlite allows ten: the sixth, eight kernel sources, cx)
cd /home/james/cortex/nk
exec ./nk ${1:-7007} egg-symbols.txt sources $(cat sources/LIST)
