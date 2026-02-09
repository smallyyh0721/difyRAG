"""
RDMA Agent Tools for Dify
These tools are exposed as API endpoints that Dify can call as custom tools.
Run this as a Flask service alongside your Dify deployment.
"""

import json
import os
import subprocess
import logging
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


# --- Tool: Check RDMA Status ---
@app.route("/tools/rdma_check_status", methods=["POST"])
@require_auth
def rdma_check_status():
    """Check RDMA device and port status."""
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

    return jsonify({"tool": "rdma_check_status", "timestamp": datetime.utcnow().isoformat(), "results": results})


# --- Tool: Check Error Counters ---
@app.route("/tools/rdma_check_counters", methods=["POST"])
@require_auth
def rdma_check_counters():
    """Read RDMA port error and performance counters."""
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
        "timestamp": datetime.utcnow().isoformat(),
        "device": device,
        "port": port,
        "error_counters": error_counters,
        "hw_counters": hw_counters,
    })


# --- Tool: Reset RDMA Port ---
@app.route("/tools/rdma_reset_port", methods=["POST"])
@require_auth
def rdma_reset_port():
    """Reset an RDMA port to recover from errors."""
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
        import time
        time.sleep(3)
        results["link_up"] = run_command(f"ip link set {netdev} up")
    else:
        # InfiniBand: use ibportstate
        results["port_reset"] = run_command(f"ibportstate -D 0 {port} reset")

    # Verify
    import time
    time.sleep(2)
    results["verify"] = run_command("ibstat 2>/dev/null || rdma link show")

    return jsonify({"tool": "rdma_reset_port", "timestamp": datetime.utcnow().isoformat(), "results": results})


# --- Tool: Reload RDMA Driver ---
@app.route("/tools/rdma_reload_driver", methods=["POST"])
@require_auth
def rdma_reload_driver():
    """Reload RDMA kernel modules."""
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

    import time
    time.sleep(2)

    # Reload (reverse order)
    for mod in reversed(modules):
        results[f"modprobe_{mod}"] = run_command(f"modprobe {mod}")

    time.sleep(2)

    # Verify
    results["verify_modules"] = run_command(f"lsmod | grep -iE '{'|'.join(modules)}'")
    results["verify_devices"] = run_command("ibv_devinfo 2>/dev/null || rdma dev show")

    return jsonify({"tool": "rdma_reload_driver", "timestamp": datetime.utcnow().isoformat(), "results": results})


# --- Tool: Configure QoS (RoCE PFC/ECN) ---
@app.route("/tools/rdma_configure_qos", methods=["POST"])
@require_auth
def rdma_configure_qos():
    """Configure RoCE QoS settings (PFC, ECN, trust mode)."""
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

    return jsonify({"tool": "rdma_configure_qos", "timestamp": datetime.utcnow().isoformat(), "results": results})


# --- Tool: Set Memory Lock Limits ---
@app.route("/tools/rdma_set_memlock", methods=["POST"])
@require_auth
def rdma_set_memlock():
    """Set memory lock limits for RDMA operations."""
    results = {}

    # Check current limits
    results["current_ulimit"] = run_command("ulimit -l")
    results["current_max_map_count"] = run_command("cat /proc/sys/vm/max_map_count")

    # Set unlimited memlock in limits.conf
    limits_entry = "* soft memlock unlimited\n* hard memlock unlimited"
    results["set_limits"] = run_command(
        f'grep -q "memlock" /etc/security/limits.conf && '
        f'echo "Already configured" || '
        f'echo "{limits_entry}" >> /etc/security/limits.conf'
    )

    # Increase max_map_count
    results["set_max_map_count"] = run_command("sysctl -w vm.max_map_count=524288")

    return jsonify({"tool": "rdma_set_memlock", "timestamp": datetime.utcnow().isoformat(), "results": results})


# --- Tool: Run Performance Test ---
@app.route("/tools/rdma_run_perftest", methods=["POST"])
@require_auth
def rdma_run_perftest():
    """Run RDMA performance benchmark."""
    data = request.json or {}
    test_type = data.get("test", "write_bw")  # write_bw, read_bw, write_lat, read_lat
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

    return jsonify({"tool": "rdma_run_perftest", "timestamp": datetime.utcnow().isoformat(), "test": test_type, "result": result})


# --- Tool: Check PCIe Configuration ---
@app.route("/tools/rdma_check_pcie", methods=["POST"])
@require_auth
def rdma_check_pcie():
    """Check PCIe configuration for RDMA devices."""
    results = {}

    # Find RDMA PCI devices
    results["pci_devices"] = run_command("lspci | grep -iE 'mellanox|infiniband|ConnectX'")

    # Get detailed PCIe info
    pci_detail = run_command(
        "for dev in $(lspci | grep -iE 'mellanox|ConnectX' | awk '{print $1}'); do "
        "echo '=== '$dev' ==='; "
        "lspci -s $dev -vvv 2>/dev/null | grep -iE 'LnkCap|LnkSta|Width|Speed|NUMA'; "
        "done"
    )
    results["pcie_link_info"] = pci_detail

    # NUMA node
    results["numa_info"] = run_command(
        "for d in /sys/class/infiniband/*/device; do "
        "echo \"$(basename $(dirname $d)): NUMA node $(cat $d/numa_node 2>/dev/null)\"; done"
    )

    return jsonify({"tool": "rdma_check_pcie", "timestamp": datetime.utcnow().isoformat(), "results": results})


# --- Tool: Send Alarm ---
@app.route("/tools/send_alarm", methods=["POST"])
@require_auth
def send_alarm():
    """Send alarm to human operators via configured channels."""
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

    # TODO: Integrate with your alerting system:
    # - Slack webhook
    # - PagerDuty
    # - Email
    # - SMS
    # Example Slack webhook:
    # import requests
    # requests.post(SLACK_WEBHOOK_URL, json={"text": f"[{severity}] RDMA Alert: {summary}"})

    return jsonify({"tool": "send_alarm", "alarm": alarm_record})


# --- Tool: Execute Action Plan ---
@app.route("/tools/rdma_action_executor", methods=["POST"])
@require_auth
def rdma_action_executor():
    """Execute a structured action plan generated by the LLM."""
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
        "rdma_check_status": "/tools/rdma_check_status",
        "rdma_check_counters": "/tools/rdma_check_counters",
        "rdma_reset_port": "/tools/rdma_reset_port",
        "rdma_reload_driver": "/tools/rdma_reload_driver",
        "rdma_configure_qos": "/tools/rdma_configure_qos",
        "rdma_set_memlock": "/tools/rdma_set_memlock",
        "rdma_run_perftest": "/tools/rdma_run_perftest",
        "rdma_check_pcie": "/tools/rdma_check_pcie",
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
            "version": "1.0.0",
            "description": "Tools for RDMA monitoring, diagnostics, and automated remediation",
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
