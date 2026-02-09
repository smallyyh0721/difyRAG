#!/usr/bin/env bash
# RDMA Log Collector
# Collects RDMA-related logs, status, and counters from a Linux server.
# Output is JSON for easy consumption by the Dify workflow.

set -euo pipefail

OUTPUT_DIR="${RDMA_LOG_DIR:-/var/log/rdma_collector}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
OUTPUT_FILE="${OUTPUT_DIR}/rdma_snapshot_$(date +%Y%m%d_%H%M%S).json"

mkdir -p "$OUTPUT_DIR"

# --- Helper: run command and capture output, return empty string on failure ---
run_cmd() {
    local result
    result=$(eval "$1" 2>&1) || true
    echo "$result"
}

# --- Collect data ---

# 1. IB device status
ibstat_output=$(run_cmd "ibstat 2>/dev/null")
ibstatus_output=$(run_cmd "ibstatus 2>/dev/null")
ibv_devinfo_output=$(run_cmd "ibv_devinfo 2>/dev/null")

# 2. RDMA link info (iproute2)
rdma_link_output=$(run_cmd "rdma link show 2>/dev/null")
rdma_dev_output=$(run_cmd "rdma dev show 2>/dev/null")
rdma_res_output=$(run_cmd "rdma res show 2>/dev/null")

# 3. Port counters from sysfs
counters_output=""
for dev_dir in /sys/class/infiniband/*/ports/*/counters; do
    if [ -d "$dev_dir" ]; then
        dev_path=$(echo "$dev_dir" | sed 's|/sys/class/infiniband/||')
        for counter_file in "$dev_dir"/*; do
            if [ -f "$counter_file" ]; then
                counter_name=$(basename "$counter_file")
                counter_val=$(cat "$counter_file" 2>/dev/null || echo "N/A")
                counters_output="${counters_output}${dev_path}/${counter_name}: ${counter_val}\n"
            fi
        done
    fi
done

# 4. RDMA-related dmesg (last 200 lines filtered)
dmesg_rdma=$(run_cmd "dmesg | grep -iE 'mlx|ib_|rdma|infiniband|roce|iwarp|qp|cq_|firmware.*error|link.*(up|down)' | tail -200")

# 5. Kernel modules
modules_output=$(run_cmd "lsmod | grep -iE 'mlx|ib_|rdma|rxe'")

# 6. PCI device info
pci_output=$(run_cmd "lspci | grep -iE 'mellanox|infiniband|ethernet.*connect'")

# 7. Network config for RDMA interfaces
net_output=""
for dev_dir in /sys/class/infiniband/*/device/net/*; do
    if [ -d "$dev_dir" ]; then
        netdev=$(basename "$dev_dir")
        ip_info=$(run_cmd "ip addr show $netdev")
        net_output="${net_output}--- ${netdev} ---\n${ip_info}\n"
    fi
done

# 8. System info
hostname_val=$(hostname 2>/dev/null || echo "unknown")
kernel_val=$(uname -r 2>/dev/null || echo "unknown")
uptime_val=$(uptime 2>/dev/null || echo "unknown")

# 9. RoCE QoS config (if mlnx_qos available)
qos_output=""
for dev_dir in /sys/class/infiniband/*/device/net/*; do
    if [ -d "$dev_dir" ]; then
        netdev=$(basename "$dev_dir")
        if command -v mlnx_qos &>/dev/null; then
            qos_output="${qos_output}--- ${netdev} ---\n$(run_cmd "mlnx_qos -i $netdev")\n"
        fi
    fi
done

# 10. Memory limits
ulimit_output=$(run_cmd "ulimit -l")
max_map_count=$(run_cmd "cat /proc/sys/vm/max_map_count")

# --- Build JSON output ---
# Using python for reliable JSON encoding
python3 -c "
import json, sys

data = {
    'timestamp': '''${TIMESTAMP}''',
    'hostname': '''${hostname_val}''',
    'kernel': '''${kernel_val}''',
    'uptime': '''${uptime_val}''',
    'ibstat': '''${ibstat_output}''',
    'ibstatus': '''${ibstatus_output}''',
    'ibv_devinfo': '''${ibv_devinfo_output}''',
    'rdma_link': '''${rdma_link_output}''',
    'rdma_dev': '''${rdma_dev_output}''',
    'rdma_res': '''${rdma_res_output}''',
    'port_counters': '''$(echo -e "$counters_output")''',
    'dmesg_rdma': '''${dmesg_rdma}''',
    'loaded_modules': '''${modules_output}''',
    'pci_devices': '''${pci_output}''',
    'network_config': '''$(echo -e "$net_output")''',
    'qos_config': '''$(echo -e "$qos_output")''',
    'ulimit_memlock': '''${ulimit_output}''',
    'max_map_count': '''${max_map_count}''',
}

with open('${OUTPUT_FILE}', 'w') as f:
    json.dump(data, f, indent=2)

print('${OUTPUT_FILE}')
"

echo "Snapshot saved to: ${OUTPUT_FILE}"
