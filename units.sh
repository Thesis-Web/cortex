#!/bin/bash
# units.sh (2026-11-02): the Cortex kernel and its page as user services on hp2, so a reboot brings the brain back from its file.
set -u
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/cortex-nk.service <<'U'
[Unit]
Description=Cortex kernel (nk) on hp2: the brain is its stored file
After=network.target

[Service]
WorkingDirectory=/home/james/cortex/nk
Environment=NK_MAP=/home/james/cortex/brain/brain.map
ExecStart=/home/james/cortex/nk/nk 7007 egg-symbols.txt sources wn gcide mwt moby map sqldoc measured guess wikt
KillSignal=SIGTERM
TimeoutStopSec=600
SuccessExitStatus=SIGTERM 143
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
U
cat > ~/.config/systemd/user/cortex-page.service <<'U'
[Unit]
Description=Cortex brain page on hp2:8058 (the kernel's own page)
After=cortex-nk.service
Requires=cortex-nk.service

[Service]
WorkingDirectory=/home/james/cortex/nk
ExecStart=/usr/bin/python3 -u -I serve8.py 8058 7007 NEURON-POINT-OF-CONNECTION-nk-2026-10-30.html LINES-nk.txt FIRST-RUNS-nk.txt 0.0.0.0
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
U
systemctl --user daemon-reload
echo "--- stop the nohup kernel (SIGTERM: it syncs and exits)"; pkill -x nk; for i in $(seq 1 120); do pgrep -x nk > /dev/null || break; sleep 1; done; tail -1 ~/cortex/brain/nk.log
systemctl --user enable --now cortex-nk.service cortex-page.service 2>&1 | tail -2
for i in $(seq 1 60); do python3 -c "import socket; socket.create_connection(('127.0.0.1', 7007), timeout=1).close()" 2>/dev/null && break; sleep 1; done
systemctl --user --no-pager status cortex-nk.service cortex-page.service 2>&1 | grep -E "Active|Main PID|nk:" | head -6
export PATH=$HOME/.local/bin:$PATH
echo "--- the brain came back from its file"; cortex status | head -3
echo "--- page"; curl -s -m 5 -o /dev/null -w "page http %{http_code}, %{size_download} bytes\n" http://127.0.0.1:8058/
echo "--- memory of the kernel"; ps -o pid,rss,etime,args -C nk | cut -c1-100
