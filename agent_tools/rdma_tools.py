"""
RDMA Agent Tools for Dify
These tools are exposed as API endpoints that Dify can call as custom tools.
Run this as a Flask service alongside your Dify deployment.

Tool Classification:
====================

Tool Types:
-----------
1. Query  : Collect debug logs and diagnostics information
2. Retune : Change settings and configuration
3. Reset  : Reset NIC or driver

Protocol Support:
-----------------
- IB   : Infiniband-specific tools
- RoCE : RoCE-specific tools
- Both : Common tools for both protocols

Tool Registry:
==============

Query Tools (Collect debug logs):
---------------------------------
- rdma_check_status       [Both]  Check RDMA device and port status
- rdma_check_counters     [Both]  Read error and performance counters
- rdma_check_pcie         [Both]  Check PCIe configuration
- rdma_check_gids         [Both]  Check GID configuration
- rdma_check_affinity     [Both]  Check CPU affinity settings
- rdma_check_qos          [RoCE]  Check QoS/PFC configuration
- rdma_check_ib_route     [IB]    Check IB routing table
- rdma_run_perftest       [Both]  Run performance benchmarks
- rdma_collect_logs       [Both]  Collect system logs
- rdma_check_memlock     [Both]  Check memory lock limits

Retune Tools (Change settings):
------------------------------
- rdma_configure_qos      [RoCE]  Configure PFC/ECN settings
- rdma_set_memlock       [Both]  Set memory lock limits
- rdma_set_irq_affinity  [Both]  Set interrupt affinity
- rdma_set_mtu           [Both]  Set MTU size
- rdma_enable_sriov       [Both]  Enable SR-IOV
- rdma_tune_performance  [Both]  Apply performance tuning

Reset Tools (Reset NIC or driver):
----------------------------------
- rdma_reset_port         [Both]  Reset RDMA port
- rdma_reload_driver      [Both]  Reload kernel modules
- rdma_reset_counters     [Both]  Reset hardware counters

Utility Tools:
--------------
- send_alarm             [Both]  Send alarm notification
- rdma_action_executor   [Both]  Execute action plans
"""

import json
import os
import subprocess
import logging
import time
from datetime import datetime
from flask import Flask, request, jsonify
from functools import wraps

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("rdma-tools")

# --- Configuration ---
ALLOWED_API_KEYS = []  # Load from config in production
DRY_RUN = False  # Set True to preview commands without executing


def load_config():
    """Load configuration from file."""
    global ALLOWED_API_KEYS, DRY_RUN
    try:
        with open("/etc/rdma-agent/tools.conf") as f:
            for line in f:
                line = line.strip()
                if line.startswith("API_KEYS="):
                    ALLOWED_API_KEYS = line.split("=", 1)[1].split(",")
                elif line.startswith("DRY_RUN="):
                    DRY_RUN = line.split("=", 1)[1].lower() == "true"
    except FileNotFoundError:
        logger.warning("Config file not found, using defaults")


def run_command(cmd, timeout=30):
    """Execute a shell command safely and return output."""
    logger.info(f"Executing: {cmd}")
    if DRY_RUN:
        return {"status": "dry_run", "command": cmd, "output": "[DRY RUN - not executed]"}
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return {
            "status": "success" if result.returncode == 0 else "error",
            "command": cmd,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "return_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "command": cmd, "error": f"Command timed out after {timeout}s"}
    except Exception as e:
        return {"status": "error", "command": cmd, "error": str(e)}


def require_auth(f):
    """Simple API key authentication decorator."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not ALLOWED_API_KEYS:
            return f(*args, **kwargs)  # No auth configured
        api_key = request.headers.get("Authorization", "").replace("Bearer ", "")
        if api_key not in ALLOWED_API_KEYS:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# =============================================================================
# QUERY TOOLS - Collect debug logs and diagnostics
# =============================================================================

# --- Query Tool: Check RDMA Status [Both] ---
@app.route("/tools/rdma_check_status", methods=["POST"])
@require_auth
def rdma_check_status():
    """
    [Type: Query] [Protocol: Both]
    Check RDMA device and port status.
    """
    results = {}
    results["ibstat"] = run_command("ibstat 2>/dev/null || echo 'ibstat not available'")
    results["rdma_link"] = run_command("rdma link show 2>/dev/null || echo 'rdma tool not available'")
    results["rdma_dev"] = run_command("rdma dev show 2>/dev/null || echo 'rdma tool not available'")

    # Port states from sysfs
    port_states = run_command(
        "for f in /sys/class/infiniband/*/ports/*/state; do "
        "echo \"$f: $(cat $f 2>/dev/null)\"; done"
    )
    results["port_states"] = port_states

    return jsonify({"tool": "rdma_check_status", "tool_type": "query", "protocol": "both",
                    "timestamp": datetime.utcnow().isoformat(), "results": results})


# --- Query Tool: Check Error Counters [Both] ---
@app.route("/tools/rdma_check_counters", methods=["POST"])
@require_auth
def rdma_check_counters():
    """
    [Type: Query] [Protocol: Both]
    Read RDMA port error and performance counters.
    """
    data = request.json or {}
    device = data.get("device", "*")
    port = data.get("port", "*")

    # Error counters
    error_counters = run_command(
        f"for f in /sys/class/infiniband/{device}/ports/{port}/counters/*; do "
        f"echo \"$(basename $f): $(cat $f 2>/dev/null)\"; done"
    )

    # Hardware counters (if available)
    hw_counters = run_command(
        f"for f in /sys/class/infiniband/{device}/ports/{port}/hw_counters/*; do "
        f"echo \"$(basename $f): $(cat $f 2>/dev/null)\"; done 2>/dev/null || echo 'N/A'"
    )

    return jsonify({
        "tool": "rdma_check_counters",
        "tool_type": "query",
        "protocol": "both",
        "timestamp": datetime.utcnow().isoformat(),
        "device": device,
        "port": port,
        "error_counters": error_counters,
        "hw_counters": hw_counters,
    })


# --- Query Tool: Check GIDs [Both] ---
@app.route("/tools/rdma_check_gids", methods=["POST"])
@require_auth
def rdma_check_gids():
    """
    [Type: Query] [Protocol: Both]
    Check GID (Global Identifier) configuration for all ports.
    """
    data = request.json or {}
    device = data.get("device", "")

    cmd = "show_gids 2>/dev/null || "
    if device:
        cmd += f"cat /sys/class/infiniband/{device}/ports/*/gids/* 2>/dev/null || "
    cmd += "for d in /sys/class/infiniband/*; do "
    cmd += "dev=$(basename $d); "
    cmd += "for p in $d/ports/*; do "
    cmd += "port=$(basename $p); "
    cmd += "echo \"Device: $dev Port: $port\"; "
    cmd += "cat $p/gids/* 2>/dev/null | head -10; "
    cmd += "done; done"

    results = {}
    results["gids"] = run_command(cmd)
    results["ip_addr"] = run_command("ip addr show 2>/dev/null | grep -E 'inet|mtu'")

    return jsonify({"tool": "rdma_check_gids", "tool_type": "query", "protocol": "both",
                    "timestamp": datetime.utcnow().isoformat(), "results": results})


# --- Query Tool: Check CPU Affinity [Both] ---
@app.route("/tools/rdma_check_affinity", methods=["POST"])
@require_auth
def rdma_check_affinity():
    """
    [Type: Query] [Protocol: Both]
    Check interrupt and RSS affinity configuration.
    """
    data = request.json or {}
    device = data.get("device", "")

    results = {}

    # Get IRQ list for device
    if device:
        results["irq_list"] = run_command(
            f"grep -l {device} /proc/irq/*/node_name 2>/dev/null | xargs -I{{}} dirname {{}} | xargs -I{{}} cat {{}}/smp_affinity_list 2>/dev/null || echo 'N/A'"
        )

    # Show all RDMA-related IRQs
    results["rdma_irqs"] = run_command(
        "cat /proc/interrupts | grep -iE 'mlx|rdma|infiniband' || echo 'No RDMA IRQs found'"
    )

    # Show current affinity
    results["irq_affinity"] = run_command(
        "for f in /proc/irq/*/smp_affinity_list; do "
        "irq=$(basename $(dirname $f)); "
        "name=$(cat /proc/irq/$irq/spurious 2>/dev/null | head -1 || echo 'unknown'); "
        "echo \"IRQ $irq: $(cat $f) [$name]\"; done | grep -v 'IRQ [0-9]*: 0' | head -50"
    )

    # NUMA info
    results["numa_hardware"] = run_command("numactl --hardware 2>/dev/null || echo 'numactl not available'")

    return jsonify({"tool": "rdma_check_affinity", "tool_type": "query", "protocol": "both",
                    "timestamp": datetime.utcnow().isoformat(), "results": results})


# --- Query Tool: Check QoS Configuration [RoCE] ---
@app.route("/tools/rdma_check_qos", methods=["POST"])
@require_auth
def rdma_check_qos():
    """
    [Type: Query] [Protocol: RoCE]
    Check QoS, PFC, and ECN configuration.
    """
    data = request.json or {}
    netdev = data.get("netdev", "")

    results = {}

    if netdev:
        results["mlnx_qos"] = run_command(f"mlnx_qos -i {netdev} 2>/dev/null || echo 'mlnx_qos not available'")
        results["ethtool_pause"] = run_command(f"ethtool -a {netdev} 2>/dev/null || echo 'ethtool not available'")
        results["ethtool_coalesce"] = run_command(f"ethtool -c {netdev} 2>/dev/null || echo 'N/A'")
        results["cable_info"] = run_command(f"ethtool --cable-diagnostics {netdev} 2>/dev/null || echo 'N/A'")
    else:
        # Show all interfaces
        results["all_interfaces"] = run_command(
            "for iface in $(ls /sys/class/net/ | grep -v lo); do "
            "echo \"=== $iface ===\"; "
            "mlnx_qos -i $iface 2>/dev/null || ethtool -a $iface 2>/dev/null || echo 'No QoS info'; "
            "done"
        )

    # Check DCBX status
    results["dcbx_status"] = run_command("dcbtool gc 2>/dev/null || echo 'dcbtool not available'")

    return jsonify({"tool": "rdma_check_qos", "tool_type": "query", "protocol": "roce",
                    "timestamp": datetime.utcnow().isoformat(), "results": results})


# --- Query Tool: Check IB Routing [IB] ---
@app.route("/tools/rdma_check_ib_route", methods=["POST"])
@require_auth
def rdma_check_ib_route():
    """
    [Type: Query] [Protocol: IB]
    Check Infiniband routing table and LID information.
    """
    results = {}

    results["ibstatus"] = run_command("ibstatus 2>/dev/null || echo 'ibstatus not available'")
    results["ibswitches"] = run_command("ibswitches 2>/dev/null || echo 'ibswitches not available'")
    results["ibhosts"] = run_command("ibhosts 2>/dev/null || echo 'ibhosts not available'")
    results["iblinkinfo"] = run_command("iblinkinfo 2>/dev/null || echo 'iblinkinfo not available'")
    results["ibdiagnet"] = run_command("ibdiagnet -ls 2>/dev/null || echo 'ibdiagnet not available'")

    # Partition keys
    results["partitions"] = run_command(
        "for f in /sys/class/infiniband/*/ports/*/pkeys/*; do "
        "echo \"$f: $(cat $f 2>/dev/null)\"; done"
    )

    return jsonify({"tool": "rdma_check_ib_route", "tool_type": "query", "protocol": "ib",
                    "timestamp": datetime.utcnow().isoformat(), "results": results})


# --- Query Tool: Collect System Logs [Both] ---
@app.route("/tools/rdma_collect_logs", methods=["POST"])
@require_auth
def rdma_collect_logs():
    """
    [Type: Query] [Protocol: Both]
    Collect RDMA-related system logs and diagnostics.
    """
    data = request.json or {}
    lines = data.get("lines", 100)

    results = {}

    # Kernel messages
    results["dmesg"] = run_command(f"dmesg | grep -iE 'mlx|rdma|infiniband' | tail -{lines}")

    # System logs
    results["syslog"] = run_command(
        f"journalctl -k | grep -iE 'mlx|rdma|infiniband' | tail -{lines} 2>/dev/null || "
        f"grep -iE 'mlx|rdma|infiniband' /var/log/messages 2>/dev/null | tail -{lines} || "
        f"echo 'No syslog available'"
    )

    # OFED version
    results["ofed_version"] = run_command("ofed_info -s 2>/dev/null || echo 'OFED not installed'")

    # Driver info
    results["driver_info"] = run_command(
        "modinfo mlx5_core 2>/dev/null | grep -E 'version:|filename:' || "
        "modinfo mlx4_core 2>/dev/null | grep -E 'version:|filename:' || "
        "echo 'Mellanox driver not found'"
    )

    # Device firmware
    results["firmware"] = run_command(
        "for d in /sys/class/infiniband/*; do "
        "dev=$(basename $d); "
        "echo \"Device: $dev\"; "
        "cat $d/fw_ver 2>/dev/null || echo 'N/A'; "
        "cat $d/hca_type 2>/dev/null || echo 'N/A'; "
        "done"
    )

    return jsonify({"tool": "rdma_collect_logs", "tool_type": "query", "protocol": "both",
                    "timestamp": datetime.utcnow().isoformat(), "results": results})


# --- Query Tool: Check Memory Lock Limits [Both] ---
@app.route("/tools/rdma_check_memlock", methods=["POST"])
@require_auth
def rdma_check_memlock():
    """
    [Type: Query] [Protocol: Both]
    Check memory lock limits for RDMA operations.
    """
    results = {}

    results["ulimit_soft"] = run_command("ulimit -S -l 2>/dev/null || echo 'N/A'")
    results["ulimit_hard"] = run_command("ulimit -H -l 2>/dev/null || echo 'N/A'")
    results["max_map_count"] = run_command("cat /proc/sys/vm/max_map_count 2>/dev/null || echo 'N/A'")
    results["limits_conf"] = run_command("grep -i memlock /etc/security/limits.conf 2>/dev/null || echo 'No memlock entry'")
    results["hugepages"] = run_command("cat /proc/sys/vm/nr_hugepages 2>/dev/null || echo 'N/A'")
    results["hugepages_free"] = run_command("cat /proc/sys/vm/nr_overcommit_hugepages 2>/dev/null || echo 'N/A'")

    return jsonify({"tool": "rdma_check_memlock", "tool_type": "query", "protocol": "both",
                    "timestamp": datetime.utcnow().isoformat(), "results": results})


# =============================================================================
# RESET TOOLS - Reset NIC or driver
# =============================================================================

# --- Reset Tool: Reset RDMA Port [Both] ---
@app.route("/tools/rdma_reset_port", methods=["POST"])
@require_auth
def rdma_reset_port():
    """
    [Type: Reset] [Protocol: Both]
    Reset an RDMA port to recover from errors.
    """
    data = request.json or {}
    device = data.get("device")
    port = data.get("port", "1")
    netdev = data.get("netdev")

    if not device and not netdev:
        return jsonify({"error": "Either 'device' or 'netdev' parameter required"}), 400

    results = {}

    if netdev:
        # RoCE: bounce the network interface
        results["link_down"] = run_command(f"ip link set {netdev} down")
        results["wait"] = {"status": "success", "output": "Waiting 3 seconds..."}
        time.sleep(3)
        results["link_up"] = run_command(f"ip link set {netdev} up")
    else:
        # InfiniBand: use ibportstate
        results["port_reset"] = run_command(f"ibportstate -D 0 {port} reset")

    # Verify
    time.sleep(2)
    results["verify"] = run_command("ibstat 2>/dev/null || rdma link show")

    return jsonify({"tool": "rdma_reset_port", "tool_type": "reset", "protocol": "both",
                    "timestamp": datetime.utcnow().isoformat(), "results": results})


# --- Reset Tool: Reload RDMA Driver [Both] ---
@app.route("/tools/rdma_reload_driver", methods=["POST"])
@require_auth
def rdma_reload_driver():
    """
    [Type: Reset] [Protocol: Both]
    Reload RDMA kernel modules.
    """
    data = request.json or {}
    driver = data.get("driver", "mlx5")

    # Determine modules to reload
    module_map = {
        "mlx5": ["mlx5_ib", "mlx5_core"],
        "mlx4": ["mlx4_ib", "mlx4_en", "mlx4_core"],
        "rxe": ["rdma_rxe"],
    }

    modules = module_map.get(driver)
    if not modules:
        return jsonify({"error": f"Unknown driver: {driver}. Supported: {list(module_map.keys())}"}), 400

    results = {}

    # Unload
    for mod in modules:
        results[f"rmmod_{mod}"] = run_command(f"modprobe -r {mod} 2>/dev/null || true")

    time.sleep(2)

    # Reload (reverse order)
    for mod in reversed(modules):
        results[f"modprobe_{mod}"] = run_command(f"modprobe {mod}")

    time.sleep(2)

    # Verify
    results["verify_modules"] = run_command(f"lsmod | grep -iE '{'|'.join(modules)}'")
    results["verify_devices"] = run_command("ibv_devinfo 2>/dev/null || rdma dev show")

    return jsonify({"tool": "rdma_reload_driver", "tool_type": "reset", "protocol": "both",
                    "timestamp": datetime.utcnow().isoformat(), "results": results})


# --- Reset Tool: Reset Counters [Both] ---
@app.route("/tools/rdma_reset_counters", methods=["POST"])
@require_auth
def rdma_reset_counters():
    """
    [Type: Reset] [Protocol: Both]
    Reset hardware counters for RDMA devices.
    """
    data = request.json or {}
    device = data.get("device", "*")
    port = data.get("port", "*")

    results = {}

    # Reset via perfquery if available
    results["perfquery_reset"] = run_command(
        f"perfquery -x -R {device} {port} 2>/dev/null || echo 'perfquery not available'"
    )

    # Reset via sysfs
    counter_reset = run_command(
        f"for f in /sys/class/infiniband/{device}/ports/{port}/counters/*; do "
        f"if [ -w \"$f\" ]; then echo 0 > \"$f\" 2>/dev/null && echo \"Reset: $f\"; fi; done"
    )
    results["sysfs_reset"] = counter_reset

    # Verify
    results["verify"] = run_command(
        f"cat /sys/class/infiniband/{device}/ports/{port}/counters/port_xmit_data 2>/dev/null || echo 'N/A'"
    )

    return jsonify({"tool": "rdma_reset_counters", "tool_type": "reset", "protocol": "both",
                    "timestamp": datetime.utcnow().isoformat(), "results": results})


# =============================================================================
# RETUNE TOOLS - Change settings and configuration
# =============================================================================

# --- Retune Tool: Configure QoS [RoCE] ---
@app.route("/tools/rdma_configure_qos", methods=["POST"])
@require_auth
def rdma_configure_qos():
    """
    [Type: Retune] [Protocol: RoCE]
    Configure RoCE QoS settings (PFC, ECN, trust mode).
    """
    data = request.json or {}
    netdev = data.get("netdev")
    if not netdev:
        return jsonify({"error": "'netdev' parameter required"}), 400

    action = data.get("action", "show")
    results = {}

    if action == "show":
        results["qos"] = run_command(f"mlnx_qos -i {netdev} 2>/dev/null || echo 'mlnx_qos not available'")
        results["ethtool_pause"] = run_command(f"ethtool -a {netdev} 2>/dev/null")

    elif action == "enable_pfc":
        pfc_string = data.get("pfc", "0,0,0,1,0,0,0,0")
        results["set_pfc"] = run_command(f"mlnx_qos -i {netdev} --pfc {pfc_string}")
        results["set_trust"] = run_command(f"mlnx_qos -i {netdev} --trust dscp")
        results["verify"] = run_command(f"mlnx_qos -i {netdev}")

    elif action == "disable_pfc":
        results["disable_pfc"] = run_command(f"mlnx_qos -i {netdev} --pfc 0,0,0,0,0,0,0,0")
        results["verify"] = run_command(f"mlnx_qos -i {netdev}")

    elif action == "enable_ecn":
        results["enable_ecn"] = run_command(f"mlnx_qos -i {netdev} --ecn 1")
        results["verify"] = run_command(f"mlnx_qos -i {netdev}")

    elif action == "set_ets":
        ets = data.get("ets", "50,30,20,0,0,0,0,0")
        results["set_ets"] = run_command(f"mlnx_qos -i {netdev} --ets {ets}")
        results["verify"] = run_command(f"mlnx_qos -i {netdev}")

    return jsonify({"tool": "rdma_configure_qos", "tool_type": "retune", "protocol": "roce",
                    "timestamp": datetime.utcnow().isoformat(), "results": results})


# --- Retune Tool: Set Memory Lock Limits [Both] ---
@app.route("/tools/rdma_set_memlock", methods=["POST"])
@require_auth
def rdma_set_memlock():
    """
    [Type: Retune] [Protocol: Both]
    Set memory lock limits for RDMA operations.
    """
    data = request.json or {}
    memlock_limit = data.get("limit", "unlimited")
    enable_hugepages = data.get("enable_hugepages", False)

    results = {}

    # Check current limits
    results["current_ulimit"] = run_command("ulimit -l")
    results["current_max_map_count"] = run_command("cat /proc/sys/vm/max_map_count")

    # Set unlimited memlock in limits.conf
    if memlock_limit == "unlimited":
        limits_entry = "* soft memlock unlimited\n* hard memlock unlimited"
    else:
        limits_entry = f"* soft memlock {memlock_limit}\n* hard memlock {memlock_limit}"

    results["set_limits"] = run_command(
        f'grep -q "memlock unlimited" /etc/security/limits.conf && '
        f'echo "Already configured" || '
        f'echo "{limits_entry}" >> /etc/security/limits.conf'
    )

    # Increase max_map_count
    results["set_max_map_count"] = run_command("sysctl -w vm.max_map_count=524288")

    # Enable hugepages if requested
    if enable_hugepages:
        results["set_hugepages"] = run_command("sysctl -w vm.nr_hugepages=1024")
        results["hugepages_status"] = run_command("cat /proc/sys/vm/nr_hugepages")

    return jsonify({"tool": "rdma_set_memlock", "tool_type": "retune", "protocol": "both",
                    "timestamp": datetime.utcnow().isoformat(), "results": results})


# --- Retune Tool: Set Interrupt Affinity [Both] ---
@app.route("/tools/rdma_set_irq_affinity", methods=["POST"])
@require_auth
def rdma_set_irq_affinity():
    """
    [Type: Retune] [Protocol: Both]
    Set interrupt affinity for RDMA devices.
    """
    data = request.json or {}
    device = data.get("device")
    cpu_range = data.get("cpu_range", "0-3")
    auto_optimize = data.get("auto_optimize", False)

    if not device:
        return jsonify({"error": "'device' parameter required"}), 400

    results = {}

    if auto_optimize:
        results["auto_optimize"] = run_command(f"mlnx_affinity -d {device} --optimize 2>/dev/null || echo 'mlnx_affinity not available'")

    # Get IRQs for device
    irq_list = run_command(
        f"grep -l {device} /proc/irq/*/node_name 2>/dev/null | cut -d'/' -f5"
    )

    if irq_list.get("status") == "success" and irq_list.get("stdout"):
        irqs = irq_list["stdout"].strip().split("\n")
        for irq in irqs:
            if irq.isdigit():
                results[f"irq_{irq}"] = run_command(f"echo {cpu_range} > /proc/irq/{irq}/smp_affinity_list")

    # Verify
    results["verify"] = run_command(
        f"for irq in $(grep -l {device} /proc/irq/*/node_name 2>/dev/null | cut -d'/' -f5); do "
        f"echo \"IRQ $irq: $(cat /proc/irq/$irq/smp_affinity_list)\"; done"
    )

    return jsonify({"tool": "rdma_set_irq_affinity", "tool_type": "retune", "protocol": "both",
                    "timestamp": datetime.utcnow().isoformat(), "results": results})


# --- Retune Tool: Set MTU [Both] ---
@app.route("/tools/rdma_set_mtu", methods=["POST"])
@require_auth
def rdma_set_mtu():
    """
    [Type: Retune] [Protocol: Both]
    Set MTU size for RDMA device.
    """
    data = request.json or {}
    device = data.get("device")
    port = data.get("port", "1")
    mtu = data.get("mtu", "9000")
    netdev = data.get("netdev")

    if not device and not netdev:
        return jsonify({"error": "Either 'device' or 'netdev' parameter required"}), 400

    results = {}

    # For RoCE, set via ip link
    if netdev:
        results["set_mtu_ip"] = run_command(f"ip link set dev {netdev} mtu {mtu}")

    # For IB, set via sysfs
    if device:
        results["set_mtu_ib"] = run_command(
            f"echo {mtu} > /sys/class/infiniband/{device}/ports/{port}/mtu 2>/dev/null || "
            f"echo 'Failed to set IB MTU'"
        )

    # Verify
    if netdev:
        results["verify_mtu"] = run_command(f"ip link show {netdev} | grep mtu")
    if device:
        results["verify_ib_mtu"] = run_command(
            f"cat /sys/class/infiniband/{device}/ports/{port}/mtu 2>/dev/null || echo 'N/A'"
        )

    return jsonify({"tool": "rdma_set_mtu", "tool_type": "retune", "protocol": "both",
                    "timestamp": datetime.utcnow().isoformat(), "results": results})


# --- Retune Tool: Enable SR-IOV [Both] ---
@app.route("/tools/rdma_enable_sriov", methods=["POST"])
@require_auth
def rdma_enable_sriov():
    """
    [Type: Retune] [Protocol: Both]
    Enable SR-IOV virtual functions.
    """
    data = request.json or {}
    device = data.get("device")
    num_vfs = data.get("num_vfs", 4)

    if not device:
        return jsonify({"error": "'device' parameter required"}), 400

    results = {}

    # Find PCI device
    pci_dev = run_command(
        f"ls -la /sys/class/infiniband/{device}/device 2>/dev/null | awk '{{print $NF}}' | xargs basename"
    )

    if pci_dev.get("status") == "success" and pci_dev.get("stdout"):
        pci = pci_dev["stdout"].strip()
        sriov_path = f"/sys/bus/pci/devices/{pci}/sriov_numvfs"

        results["current_vfs"] = run_command(f"cat {sriov_path} 2>/dev/null || echo '0'")
        results["enable_sriov"] = run_command(f"echo {num_vfs} > {sriov_path} 2>&1")
        results["verify_vfs"] = run_command(f"cat {sriov_path} 2>/dev/null || echo 'N/A'")
        results["list_vfs"] = run_command(f"lspci | grep -i 'virtual function' | grep -i '{pci[:4]}' || echo 'No VFs found'")

    return jsonify({"tool": "rdma_enable_sriov", "tool_type": "retune", "protocol": "both",
                    "timestamp": datetime.utcnow().isoformat(), "results": results})


# --- Retune Tool: Performance Tuning [Both] ---
@app.route("/tools/rdma_tune_performance", methods=["POST"])
@require_auth
def rdma_tune_performance():
    """
    [Type: Retune] [Protocol: Both]
    Apply performance tuning parameters.
    """
    data = request.json or {}
    profile = data.get("profile", "balanced")  # low-latency, throughput, balanced

    results = {}

    if profile == "low-latency":
        # Low latency profile
        results["disable_irqbalance"] = run_command("systemctl stop irqbalance 2>/dev/null || echo 'irqbalance not running'")
        results["set_swappiness"] = run_command("sysctl -w vm.swappiness=10")
        results["disable_numa_balancing"] = run_command("sysctl -w kernel.numa_balancing=0")

    elif profile == "throughput":
        # Throughput profile
        results["enable_irqbalance"] = run_command("systemctl start irqbalance 2>/dev/null || echo 'irqbalance not available'")
        results["set_swappiness"] = run_command("sysctl -w vm.swappiness=30")
        results["tcp_tuning"] = run_command(
            "sysctl -w net.core.rmem_max=134217728 && "
            "sysctl -w net.core.wmem_max=134217728 && "
            "sysctl -w net.ipv4.tcp_rmem='4096 87380 134217728' && "
            "sysctl -w net.ipv4.tcp_wmem='4096 65536 134217728'"
        )

    elif profile == "balanced":
        # Balanced profile
        results["set_swappiness"] = run_command("sysctl -w vm.swappiness=20")
        results["enable_numa_balancing"] = run_command("sysctl -w kernel.numa_balancing=1")

    # Common settings
    results["max_map_count"] = run_command("sysctl -w vm.max_map_count=524288")

    # Use mlnx_tune if available
    results["mlnx_tune"] = run_command(f"mlnx_tune --profile {profile} 2>/dev/null || echo 'mlnx_tune not available'")

    return jsonify({"tool": "rdma_tune_performance", "tool_type": "retune", "protocol": "both",
                    "timestamp": datetime.utcnow().isoformat(), "results": results})


# --- Query Tool: Run Performance Test [Both] ---
@app.route("/tools/rdma_run_perftest", methods=["POST"])
@require_auth
def rdma_run_perftest():
    """
    [Type: Query] [Protocol: Both]
    Run RDMA performance benchmark.
    """
    data = request.json or {}
    test_type = data.get("test", "write_bw")
    device = data.get("device", "")
    remote_host = data.get("remote_host", "")
    duration = data.get("duration", 5)

    test_map = {
        "write_bw": "ib_write_bw",
        "read_bw": "ib_read_bw",
        "write_lat": "ib_write_lat",
        "read_lat": "ib_read_lat",
        "send_bw": "ib_send_bw",
        "send_lat": "ib_send_lat",
    }

    cmd_name = test_map.get(test_type)
    if not cmd_name:
        return jsonify({"error": f"Unknown test type: {test_type}. Supported: {list(test_map.keys())}"}), 400

    cmd = cmd_name
    if device:
        cmd += f" -d {device}"
    cmd += f" -D {duration} --report_gbits"
    if remote_host:
        cmd += f" {remote_host}"

    result = run_command(cmd, timeout=duration + 30)

    return jsonify({"tool": "rdma_run_perftest", "tool_type": "query", "protocol": "both",
                    "timestamp": datetime.utcnow().isoformat(), "test": test_type, "result": result})


# --- Query Tool: Check PCIe Configuration [Both] ---
@app.route("/tools/rdma_check_pcie", methods=["POST"])
@require_auth
def rdma_check_pcie():
    """
    [Type: Query] [Protocol: Both]
    Check PCIe configuration for RDMA devices.
    """
    results = {}

    # Find RDMA PCI devices
    results["pci_devices"] = run_command("lspci | grep -iE 'mellanox|infiniband|ConnectX'")

    # Get detailed PCIe info
    pci_detail = run_command(
        "for dev in $(lspci | grep -iE 'mellanox|ConnectX' | awk '{print $1}'); do "
        "echo '==='$dev'==='; "
        "lspci -s $dev -vvv 2>/dev/null | grep -iE 'LnkCap|LnkSta|Width|Speed|NUMA'; "
        "done"
    )
    results["pcie_link_info"] = pci_detail

    # NUMA node
    results["numa_info"] = run_command(
        "for d in /sys/class/infiniband/*/device; do "
        "echo \"$(basename $(dirname $d)): NUMA node $(cat $d/numa_node 2>/dev/null)\"; done"
    )

    return jsonify({"tool": "rdma_check_pcie", "tool_type": "query", "protocol": "both",
                    "timestamp": datetime.utcnow().isoformat(), "results": results})


# =============================================================================
# UTILITY TOOLS
# =============================================================================

# --- Utility Tool: Send Alarm [Both] ---
@app.route("/tools/send_alarm", methods=["POST"])
@require_auth
def send_alarm():
    """
    [Type: Utility] [Protocol: Both]
    Send alarm to human operators via configured channels.
    """
    data = request.json or {}
    severity = data.get("severity", "warning")
    summary = data.get("summary", "RDMA issue detected")
    details = data.get("details", "")

    alarm_record = {
        "timestamp": datetime.utcnow().isoformat(),
        "severity": severity,
        "summary": summary,
        "details": details,
        "status": "sent",
    }

    # Log the alarm
    logger.warning(f"ALARM [{severity}]: {summary}")

    # Write to alarm log file
    log_dir = os.environ.get("RDMA_LOG_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"))
    os.makedirs(log_dir, exist_ok=True)
    try:
        with open(os.path.join(log_dir, "alarms.json"), "a") as f:
            f.write(json.dumps(alarm_record) + "\n")
    except Exception as e:
        logger.error(f"Failed to write alarm log: {e}")

    return jsonify({"tool": "send_alarm", "tool_type": "utility", "protocol": "both",
                    "alarm": alarm_record})


# --- Utility Tool: Execute Action Plan [Both] ---
@app.route("/tools/rdma_action_executor", methods=["POST"])
@require_auth
def rdma_action_executor():
    """
    [Type: Utility] [Protocol: Both]
    Execute a structured action plan generated by the LLM.
    """
    data = request.json or {}
    action_plan = data.get("action_plan", {})

    if isinstance(action_plan, str):
        try:
            action_plan = json.loads(action_plan)
        except json.JSONDecodeError:
            return jsonify({"error": "Invalid action_plan JSON"}), 400

    steps = action_plan.get("plan", [])
    max_retries = action_plan.get("max_retries", 3)
    results = []

    # Tool endpoint mapping
    tool_endpoints = {
        # Query tools
        "rdma_check_status": "/tools/rdma_check_status",
        "rdma_check_counters": "/tools/rdma_check_counters",
        "rdma_check_pcie": "/tools/rdma_check_pcie",
        "rdma_check_gids": "/tools/rdma_check_gids",
        "rdma_check_affinity": "/tools/rdma_check_affinity",
        "rdma_check_qos": "/tools/rdma_check_qos",
        "rdma_check_ib_route": "/tools/rdma_check_ib_route",
        "rdma_run_perftest": "/tools/rdma_run_perftest",
        "rdma_collect_logs": "/tools/rdma_collect_logs",
        "rdma_check_memlock": "/tools/rdma_check_memlock",
        # Retune tools
        "rdma_configure_qos": "/tools/rdma_configure_qos",
        "rdma_set_memlock": "/tools/rdma_set_memlock",
        "rdma_set_irq_affinity": "/tools/rdma_set_irq_affinity",
        "rdma_set_mtu": "/tools/rdma_set_mtu",
        "rdma_enable_sriov": "/tools/rdma_enable_sriov",
        "rdma_tune_performance": "/tools/rdma_tune_performance",
        # Reset tools
        "rdma_reset_port": "/tools/rdma_reset_port",
        "rdma_reload_driver": "/tools/rdma_reload_driver",
        "rdma_reset_counters": "/tools/rdma_reset_counters",
        # Utility tools
        "send_alarm": "/tools/send_alarm",
    }

    for step in steps:
        tool_name = step.get("tool")
        params = step.get("parameters", {})
        step_num = step.get("step", "?")

        logger.info(f"Executing step {step_num}: {step.get('description', tool_name)}")

        if tool_name not in tool_endpoints:
            results.append({
                "step": step_num,
                "tool": tool_name,
                "status": "error",
                "error": f"Unknown tool: {tool_name}",
            })
            continue

        # Call the tool endpoint internally
        with app.test_request_context(
            tool_endpoints[tool_name],
            method="POST",
            json=params,
            content_type="application/json",
        ):
            try:
                endpoint_func = app.view_functions[tool_name]
                response = endpoint_func()
                if hasattr(response, "get_json"):
                    result_data = response.get_json()
                else:
                    result_data = response[0].get_json() if isinstance(response, tuple) else {"raw": str(response)}

                results.append({
                    "step": step_num,
                    "tool": tool_name,
                    "status": "success",
                    "result": result_data,
                })
            except Exception as e:
                results.append({
                    "step": step_num,
                    "tool": tool_name,
                    "status": "error",
                    "error": str(e),
                })

    return jsonify({
        "tool": "rdma_action_executor",
        "tool_type": "utility",
        "protocol": "both",
        "timestamp": datetime.utcnow().isoformat(),
        "steps_total": len(steps),
        "steps_success": sum(1 for r in results if r["status"] == "success"),
        "steps_failed": sum(1 for r in results if r["status"] == "error"),
        "results": results,
    })


# --- OpenAPI Schema for Dify Custom Tool Import ---
@app.route("/openapi.json", methods=["GET"])
def openapi_schema():
    """Serve OpenAPI schema for Dify custom tool import."""
    schema = {
        "openapi": "3.0.0",
        "info": {
            "title": "RDMA Agent Tools",
            "version": "2.0.0",
            "description": "Tools for RDMA monitoring, diagnostics, and automated remediation. "
                           "Tools are classified by type (Query/Retune/Reset) and protocol (IB/RoCE/Both).",
        },
        "servers": [{"url": "http://localhost:5100"}],
        "paths": {
            "/tools/rdma_check_status": {
                "post": {
                    "operationId": "rdma_check_status",
                    "summary": "Check RDMA device and port status",
                    "requestBody": {"content": {"application/json": {"schema": {"type": "object"}}}},
                    "responses": {"200": {"description": "RDMA status information"}},
                }
            },
            "/tools/rdma_check_counters": {
                "post": {
                    "operationId": "rdma_check_counters",
                    "summary": "Read RDMA error and performance counters",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "device": {"type": "string", "description": "Device name (e.g., mlx5_0). Default: all"},
                                        "port": {"type": "string", "description": "Port number. Default: all"},
                                    },
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "Counter values"}},
                }
            },
            "/tools/rdma_reset_port": {
                "post": {
                    "operationId": "rdma_reset_port",
                    "summary": "Reset an RDMA port to recover from errors",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "device": {"type": "string", "description": "IB device name"},
                                        "port": {"type": "string", "description": "Port number", "default": "1"},
                                        "netdev": {"type": "string", "description": "Network device name (for RoCE)"},
                                    },
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "Reset results"}},
                }
            },
            "/tools/rdma_reload_driver": {
                "post": {
                    "operationId": "rdma_reload_driver",
                    "summary": "Reload RDMA kernel modules",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "driver": {
                                            "type": "string",
                                            "description": "Driver family: mlx5, mlx4, or rxe",
                                            "default": "mlx5",
                                        }
                                    },
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "Driver reload results"}},
                }
            },
            "/tools/rdma_configure_qos": {
                "post": {
                    "operationId": "rdma_configure_qos",
                    "summary": "Configure RoCE QoS settings (PFC/ECN)",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["netdev"],
                                    "properties": {
                                        "netdev": {"type": "string", "description": "Network device name"},
                                        "action": {
                                            "type": "string",
                                            "enum": ["show", "enable_pfc", "disable_pfc"],
                                            "default": "show",
                                        },
                                        "pfc": {"type": "string", "description": "PFC bitmap", "default": "0,0,0,1,0,0,0,0"},
                                    },
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "QoS configuration results"}},
                }
            },
            "/tools/rdma_set_memlock": {
                "post": {
                    "operationId": "rdma_set_memlock",
                    "summary": "Set memory lock limits for RDMA",
                    "requestBody": {"content": {"application/json": {"schema": {"type": "object"}}}},
                    "responses": {"200": {"description": "Memlock configuration results"}},
                }
            },
            "/tools/rdma_run_perftest": {
                "post": {
                    "operationId": "rdma_run_perftest",
                    "summary": "Run RDMA performance benchmark",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "test": {
                                            "type": "string",
                                            "enum": ["write_bw", "read_bw", "write_lat", "read_lat", "send_bw", "send_lat"],
                                            "default": "write_bw",
                                        },
                                        "device": {"type": "string", "description": "RDMA device name"},
                                        "remote_host": {"type": "string", "description": "Remote host for test"},
                                        "duration": {"type": "integer", "default": 5},
                                    },
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "Performance test results"}},
                }
            },
            "/tools/rdma_check_pcie": {
                "post": {
                    "operationId": "rdma_check_pcie",
                    "summary": "Check PCIe configuration for RDMA devices",
                    "requestBody": {"content": {"application/json": {"schema": {"type": "object"}}}},
                    "responses": {"200": {"description": "PCIe configuration info"}},
                }
            },
            "/tools/send_alarm": {
                "post": {
                    "operationId": "send_alarm",
                    "summary": "Send alarm to human operators",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "severity": {"type": "string", "enum": ["info", "warning", "critical"]},
                                        "summary": {"type": "string"},
                                        "details": {"type": "string"},
                                    },
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "Alarm sent confirmation"}},
                }
            },
        },
    }
    return jsonify(schema)


if __name__ == "__main__":
    load_config()
    app.run(host="0.0.0.0", port=5100, debug=False)
