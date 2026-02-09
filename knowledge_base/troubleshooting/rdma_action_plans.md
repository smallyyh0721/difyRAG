# RDMA Action Plans for Automated Agent

This document provides structured action plans that the agent can follow to diagnose and fix RDMA issues.

---

## Action Plan: Port Down Recovery

**Trigger:** Port state detected as "Down" or "Initializing"

**Steps:**
1. **Check physical state**
   - Command: `cat /sys/class/infiniband/*/ports/*/phys_state`
   - If "Polling": cable may be disconnected or link partner down
   - If "Disabled": port administratively disabled

2. **Check driver status**
   - Command: `lsmod | grep mlx`
   - If no driver loaded: `modprobe mlx5_ib` (or mlx4_ib)

3. **Check dmesg for errors**
   - Command: `dmesg | tail -50 | grep -iE "mlx|ib_|link|error|fail"`
   - Look for firmware errors, cable detection issues

4. **Attempt link reset**
   - Command: `ibportstate -D 0 1 reset` (for InfiniBand)
   - Or: `ip link set <netdev> down && sleep 2 && ip link set <netdev> up` (for RoCE)

5. **Verify recovery**
   - Command: `ibstat`
   - Expected: State "Active", Physical state "LinkUp"

**Escalation:** If port remains down after reset, alert human operator - likely hardware issue.

---

## Action Plan: Performance Degradation

**Trigger:** Bandwidth or latency outside expected baseline

**Steps:**
1. **Measure current performance**
   - Command: `ib_write_bw -d <dev> -D 5 --report_gbits <remote>`
   - Record result, compare against baseline

2. **Check link rate**
   - Command: `ibstat | grep -E "Rate|Width"`
   - Verify running at expected rate (e.g., 100 Gbps HDR, 200 Gbps HDR100)

3. **Check error counters**
   - Command: `cat /sys/class/infiniband/*/ports/*/counters/symbol_error`
   - Command: `cat /sys/class/infiniband/*/ports/*/counters/port_rcv_errors`
   - Non-zero and increasing = physical layer issue

4. **Check PCIe**
   - Command: `lspci -s <bdf> -vvv | grep -iE "width|speed|lnk"`
   - Verify PCIe link width and speed match device capability

5. **Check NUMA affinity**
   - Command: `cat /sys/class/infiniband/*/device/numa_node`
   - Ensure application runs on same NUMA node

6. **Check for congestion (RoCE)**
   - Command: `ethtool -S <netdev> | grep -iE "pause|pfc|ecn|cnp"`
   - High pause frame count indicates congestion

**Escalation:** If physical errors detected, alert for cable/HW inspection.

---

## Action Plan: Connection Failure

**Trigger:** Application reports connection timeout or QP error

**Steps:**
1. **Check basic connectivity**
   - Command: `ibping -S` (server) / `ibping <lid>` (client) for IB
   - Command: `ping <remote_ip>` for RoCE

2. **Check QP state**
   - Command: `rdma res show qp`
   - Look for QPs in ERROR state

3. **Check GID table (RoCE)**
   - Command: `ibv_devinfo -v | grep GID`
   - Verify valid GID entries exist

4. **Check subnet manager (InfiniBand)**
   - Command: `sminfo`
   - If no SM: start opensm or check fabric SM

5. **Verify memory limits**
   - Command: `ulimit -l`
   - If not unlimited: `ulimit -l unlimited`

6. **Reset RDMA interface**
   - Command: Reload driver module as last resort

**Escalation:** If connectivity fails at IP level, escalate to network team.

---

## Action Plan: Memory Registration Failure

**Trigger:** Application reports MR registration failure

**Steps:**
1. **Check locked memory limit**
   - Command: `ulimit -l`
   - Fix: Add to `/etc/security/limits.conf`:
     ```
     * soft memlock unlimited
     * hard memlock unlimited
     ```

2. **Check max_map_count**
   - Command: `sysctl vm.max_map_count`
   - Fix: `sysctl -w vm.max_map_count=524288`

3. **Check available memory**
   - Command: `free -h`
   - If low memory: identify and resolve memory pressure

4. **Check hugepages (if used)**
   - Command: `cat /proc/meminfo | grep -i huge`
   - Verify sufficient hugepages allocated

**Escalation:** If memory is genuinely exhausted, alert for capacity planning.

---

## Action Plan: RoCE Lossless Configuration

**Trigger:** RoCE packet drops detected or PFC not configured

**Steps:**
1. **Check current QoS configuration**
   - Command: `mlnx_qos -i <netdev>`

2. **Enable PFC on priority 3 (RDMA traffic)**
   - Command: `mlnx_qos -i <netdev> --pfc 0,0,0,1,0,0,0,0`

3. **Set trust mode to DSCP**
   - Command: `mlnx_qos -i <netdev> --trust dscp`

4. **Configure ECN**
   - Command: `echo 1 > /sys/kernel/debug/mlx5/<pci>/cc_params/np_cnp_dscp`

5. **Verify configuration**
   - Command: `mlnx_qos -i <netdev>`
   - Check PFC enabled on correct priority

6. **Test under load**
   - Command: `ib_write_bw -d <dev> -D 10 --report_gbits <remote>`
   - Monitor drops: `ethtool -S <netdev> | grep drop`

**Escalation:** Switch-side PFC/ECN configuration requires network admin.

---

## Action Plan: Driver/Firmware Recovery

**Trigger:** Device not visible or firmware errors in dmesg

**Steps:**
1. **Check PCI device visibility**
   - Command: `lspci | grep -i mellanox`
   - If not visible: PCIe issue, needs hardware check

2. **Check current firmware**
   - Command: `cat /sys/class/infiniband/*/fw_ver` or `mlxfwmanager --query`

3. **Check for firmware errors**
   - Command: `dmesg | grep -iE "firmware|health|fatal|assert"`

4. **Reload driver**
   - Command: `modprobe -r mlx5_ib mlx5_core && sleep 2 && modprobe mlx5_core mlx5_ib`

5. **If firmware issue persists, attempt reset**
   - Command: `mlxfwreset -d <dev> -y reset`
   - Note: This will cause brief network disruption

**Escalation:** Firmware update or hardware replacement requires human authorization.
