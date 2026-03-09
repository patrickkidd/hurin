#!/usr/bin/env bash
# ops-heartbeat.sh — deterministic health checks for hurin heartbeat
# Returns HEARTBEAT_OK if everything is fine, or HEARTBEAT_ALERT + details if not.

set -euo pipefail

alerts=()

# --- Service health ---
services=(openclaw-gateway openclaw-taskdaemon openclaw-teamlead)
for svc in "${services[@]}"; do
    status=$(systemctl --user is-active "$svc" 2>/dev/null || true)
    if [[ "$status" != "active" ]]; then
        # Attempt restart
        systemctl --user restart "$svc" 2>/dev/null || true
        sleep 2
        new_status=$(systemctl --user is-active "$svc" 2>/dev/null || true)
        if [[ "$new_status" == "active" ]]; then
            alerts+=("$svc was down, auto-restarted successfully")
        else
            alerts+=("$svc is DOWN and restart failed (status: $new_status)")
        fi
    fi
done

# --- Stuck tasks ---
registry="$HOME/.openclaw/workspace-hurin/theapp/.clawdbot/active-tasks.json"
if [[ -f "$registry" ]]; then
    one_hour_ago=$(date -d '1 hour ago' +%s 2>/dev/null || date -v-1H +%s 2>/dev/null)
    # Find running tasks with stale logs
    running_tasks=$(python3 -c "
import json, os, time
with open('$registry') as f:
    reg = json.load(f)
cutoff = time.time() - 3600
stale = []
for tid, info in reg.items():
    if info.get('status') == 'running':
        log = os.path.expanduser(f'~/.openclaw/monitor/task-logs/{tid}.log')
        if os.path.exists(log):
            mtime = os.path.getmtime(log)
            if mtime < cutoff:
                mins = int((time.time() - mtime) / 60)
                stale.append(f'{tid} (no log activity for {mins}m)')
        else:
            stale.append(f'{tid} (no log file)')
for s in stale:
    print(s)
" 2>/dev/null || true)
    while IFS= read -r line; do
        [[ -n "$line" ]] && alerts+=("Stuck task: $line")
    done <<< "$running_tasks"
fi

# --- Disk space ---
disk_pct=$(df / --output=pcent 2>/dev/null | tail -1 | tr -d ' %')
if [[ -n "$disk_pct" ]] && (( disk_pct >= 90 )); then
    alerts+=("Disk usage at ${disk_pct}%")
fi

# --- Memory pressure ---
mem_avail_mb=$(awk '/MemAvailable/ {printf "%d", $2/1024}' /proc/meminfo 2>/dev/null || true)
if [[ -n "$mem_avail_mb" ]] && (( mem_avail_mb < 200 )); then
    alerts+=("Low memory: only ${mem_avail_mb}MB available")
fi

# --- Output ---
if (( ${#alerts[@]} == 0 )); then
    echo "HEARTBEAT_OK"
else
    echo "HEARTBEAT_ALERT"
    for alert in "${alerts[@]}"; do
        echo "- $alert"
    done
fi
