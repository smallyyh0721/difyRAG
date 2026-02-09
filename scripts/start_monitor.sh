#!/usr/bin/env bash
# Start the RDMA Monitor Daemon
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load environment
if [ -f "$PROJECT_DIR/config/.env" ]; then
    export $(grep -v '^#' "$PROJECT_DIR/config/.env" | xargs)
fi

echo "Starting RDMA Monitor Daemon..."
exec "$PROJECT_DIR/collector/rdma_monitor_daemon.sh"
