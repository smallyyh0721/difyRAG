#!/usr/bin/env bash
# RDMA Monitor Daemon
# Periodically collects RDMA state and sends to Dify workflow API
# for analysis and automated action.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config/monitor.conf"

# Defaults (overridden by config file)
DIFY_API_URL="${DIFY_API_URL:-http://localhost/v1/workflows/run}"
DIFY_API_KEY="${DIFY_API_KEY:-}"
CHECK_INTERVAL="${CHECK_INTERVAL:-60}"  # seconds
LOG_DIR="${RDMA_LOG_DIR:-/var/log/rdma_collector}"
MONITOR_LOG="${LOG_DIR}/monitor.log"

# Load config if exists
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] $1" | tee -a "$MONITOR_LOG"
}

# Quick health check: returns non-zero if issues detected
check_rdma_health() {
    local issues=""

    # Check if any IB device exists
    if [ ! -d /sys/class/infiniband ]; then
        echo "NO_IB_DEVICES"
        return 1
    fi

    # Check port states
    for state_file in /sys/class/infiniband/*/ports/*/state; do
        if [ -f "$state_file" ]; then
            state=$(cat "$state_file" 2>/dev/null || echo "unknown")
            if [[ "$state" != *"ACTIVE"* ]]; then
                dev_port=$(echo "$state_file" | sed 's|/sys/class/infiniband/||;s|/state||')
                issues="${issues}PORT_NOT_ACTIVE:${dev_port};"
            fi
        fi
    done

    # Check error counters (non-zero = potential issue)
    for counter_dir in /sys/class/infiniband/*/ports/*/counters; do
        if [ -d "$counter_dir" ]; then
            for err_counter in symbol_error link_error_recovery link_downed \
                               port_rcv_errors port_xmit_discards \
                               local_link_integrity_errors \
                               excessive_buffer_overrun_errors; do
                counter_file="${counter_dir}/${err_counter}"
                if [ -f "$counter_file" ]; then
                    val=$(cat "$counter_file" 2>/dev/null || echo "0")
                    if [ "$val" != "0" ] && [ "$val" != "N/A" ]; then
                        dev_port=$(echo "$counter_dir" | sed 's|/sys/class/infiniband/||;s|/counters||')
                        issues="${issues}ERROR_COUNTER:${dev_port}/${err_counter}=${val};"
                    fi
                fi
            done
        fi
    done

    if [ -n "$issues" ]; then
        echo "$issues"
        return 1
    fi

    echo "HEALTHY"
    return 0
}

# Send snapshot to Dify workflow
send_to_dify() {
    local snapshot_file="$1"
    local health_status="$2"

    if [ -z "$DIFY_API_KEY" ]; then
        log "ERROR: DIFY_API_KEY not set. Skipping API call."
        return 1
    fi

    local snapshot_content
    snapshot_content=$(cat "$snapshot_file")

    local payload
    payload=$(python3 -c "
import json
data = {
    'inputs': {
        'rdma_snapshot': json.dumps(json.loads(open('${snapshot_file}').read())),
        'health_status': '${health_status}',
        'mode': 'auto_monitor'
    },
    'response_mode': 'blocking',
    'user': 'rdma-monitor-daemon'
}
print(json.dumps(data))
")

    local response
    response=$(curl -s -w "\n%{http_code}" \
        -X POST "$DIFY_API_URL" \
        -H "Authorization: Bearer $DIFY_API_KEY" \
        -H "Content-Type: application/json" \
        -d "$payload" \
        --max-time 120)

    local http_code
    http_code=$(echo "$response" | tail -1)
    local body
    body=$(echo "$response" | head -n -1)

    if [ "$http_code" = "200" ]; then
        log "Dify workflow executed successfully"
        echo "$body" >> "${LOG_DIR}/dify_responses.log"
    else
        log "ERROR: Dify API returned HTTP ${http_code}: ${body}"
        return 1
    fi
}

# --- Main loop ---
log "RDMA Monitor Daemon starting (interval: ${CHECK_INTERVAL}s)"

while true; do
    log "Running health check..."

    health_result=$(check_rdma_health) || true
    health_exit=$?

    if [ $health_exit -ne 0 ]; then
        log "Issues detected: ${health_result}"
        log "Collecting full snapshot..."

        snapshot_file=$("${SCRIPT_DIR}/rdma_log_collector.sh")

        log "Sending to Dify for analysis..."
        send_to_dify "$snapshot_file" "$health_result" || \
            log "Failed to send to Dify. Will retry next cycle."
    else
        log "Health check: OK"
    fi

    sleep "$CHECK_INTERVAL"
done
