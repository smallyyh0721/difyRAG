#!/usr/bin/env bash
# Start the RDMA Agent Tools API service
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load environment
if [ -f "$PROJECT_DIR/config/.env" ]; then
    export $(grep -v '^#' "$PROJECT_DIR/config/.env" | xargs)
fi

HOST="${AGENT_TOOLS_HOST:-0.0.0.0}"
PORT="${AGENT_TOOLS_PORT:-5100}"

cd "$PROJECT_DIR/agent_tools"

echo "Starting RDMA Agent Tools service on ${HOST}:${PORT}"
exec gunicorn \
    --bind "${HOST}:${PORT}" \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    rdma_tools:app
