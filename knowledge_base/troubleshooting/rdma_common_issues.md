# RDMA Common Issues and Troubleshooting Guide

## 1. Link Layer Issues

### Port Down / Physical Link Failure
**Symptoms:**
- `ibstat` shows port state as "Down"
- `dmesg` shows link down messages
- No connectivity to remote hosts

**Diagnosis:**
```bash
ibstat
ibstatus
dmesg | grep -i "link\|ib\|mlx"
cat /sys/class/infiniband/*/ports/*/state
```

**Common Causes & Fixes:**
- Cable disconnected or damaged → Reseat or replace cable
- SFP/QSFP module failure → Replace transceiver module
- Switch port issue → Check switch port status, try different port
- Driver not loaded → `modprobe mlx5_ib` or `modprobe mlx4_ib`

### Port Active but Not Operational
**Symptoms:**
- Port state is "Active" but `phys_state` is not "LinkUp"
- Intermittent connectivity

**Diagnosis:**
```bash
cat /sys/class/infiniband/*/ports/*/phys_state
ethtool <netdev>
mlnx_qos -i <netdev>
```

**Fixes:**
- Check speed/width negotiation: `ibstat | grep -E "Rate|Width"`
- Verify subnet manager is running (InfiniBand): `sminfo`
- For RoCE: verify DCBX/PFC configuration

---

## 2. Performance Issues

### Low Bandwidth
**Symptoms:**
- `ib_write_bw` or `ib_read_bw` shows lower than expected throughput
- Application reports slow data transfer

**Diagnosis:**
```bash
ib_write_bw -d <dev> --report_gbits <remote_host>
ibstat  # Check link rate/width
cat /sys/class/infiniband/*/ports/*/rate
ethtool -S <netdev> | grep -i err
```

**Common Causes & Fixes:**
- Link running at reduced width → Check cable, clean connectors
- PCIe bottleneck → Verify PCIe slot gen/width: `lspci -vvv | grep -i width`
- CPU affinity issues → Use `numactl` to pin to correct NUMA node
- MTU mismatch → Set consistent MTU across path
- Congestion → Enable ECN for RoCE: `mlnx_qos -i <dev> --trust dscp`

### High Latency
**Symptoms:**
- `ib_write_lat` or `ib_read_lat` shows unexpectedly high latency
- Application response times degraded

**Diagnosis:**
```bash
ib_write_lat -d <dev> <remote_host>
cat /proc/interrupts | grep mlx
lstopo  # Check NUMA topology
```

**Fixes:**
- Verify NUMA locality: process and NIC on same NUMA node
- Disable CPU power states: `cpupower frequency-set -g performance`
- Check for interrupt coalescing: `ethtool -c <netdev>`
- Verify no software path fallback (check for RNR retries)

---

## 3. Connection Issues

### QP State Errors
**Symptoms:**
- Applications fail with "Transport retry counter exceeded"
- QP moves to ERROR state
- Connection setup fails

**Diagnosis:**
```bash
rdma res show qp
cat /sys/class/infiniband/*/ports/*/counters/*
dmesg | grep -i "qp\|cq\|rdma"
```

**Common Causes & Fixes:**
- Remote host unreachable → Verify network connectivity
- Timeout values too low → Increase QP timeout parameter
- MTU mismatch → Align path MTU on both sides
- GID table issues (RoCE) → Verify GID table: `ibv_devinfo -v | grep GID`

### RNR (Receiver Not Ready) Errors
**Symptoms:**
- `rnr_retry_exceeded` errors in dmesg
- Performance degradation with retries

**Diagnosis:**
```bash
cat /sys/class/infiniband/*/ports/*/counters/port_rcv_remote_physical_errors
rdma statistic show
```

**Fixes:**
- Increase RNR retry count in QP attributes
- Increase receive queue depth
- Pre-post sufficient receive buffers

---

## 4. Memory Registration Issues

### MR Registration Failure
**Symptoms:**
- `ibv_reg_mr()` returns NULL / error
- "Cannot allocate memory" errors
- Application startup failures

**Diagnosis:**
```bash
ulimit -l  # Check locked memory limit
cat /proc/meminfo | grep -i locked
cat /proc/sys/vm/max_map_count
```

**Fixes:**
- Increase locked memory limit: `ulimit -l unlimited` or edit `/etc/security/limits.conf`
- Increase max_map_count: `sysctl -w vm.max_map_count=262144`
- Reduce registration size or use ODP (On-Demand Paging)

---

## 5. RoCE-Specific Issues

### PFC/ECN Misconfiguration
**Symptoms:**
- Packet drops under load
- Performance drops with multiple flows
- `ethtool -S` shows pause frame issues

**Diagnosis:**
```bash
mlnx_qos -i <netdev>
ethtool -S <netdev> | grep -i "pause\|pfc\|ecn\|drop"
lldptool -ti <netdev> -V PFC
```

**Fixes:**
- Enable PFC on correct priority: `mlnx_qos -i <dev> --pfc 0,0,0,1,0,0,0,0`
- Configure ECN: `sysctl -w net.ipv4.tcp_ecn=1`
- Set trust mode to DSCP: `mlnx_qos -i <dev> --trust dscp`
- Verify switch PFC/ECN configuration matches host

### GID Table Issues
**Symptoms:**
- RoCE v2 connections fail
- "No route to host" for RDMA operations

**Diagnosis:**
```bash
ibv_devinfo -v | grep GID
rdma link show
show_gids  # from rdma-core
```

**Fixes:**
- Verify correct RoCE version: `cma_roce_mode -d <dev> -p <port>`
- Check IP address assignment on RDMA interface
- Verify routing for RoCE v2 traffic

---

## 6. Driver and Firmware Issues

### Driver Load Failure
**Symptoms:**
- No RDMA devices visible (`ibv_devinfo` shows nothing)
- Module load errors in dmesg

**Diagnosis:**
```bash
lsmod | grep -i "mlx\|ib_\|rdma"
dmesg | grep -i "mlx\|firmware\|ib_"
lspci | grep -i mellanox
```

**Fixes:**
- Install correct driver package (MLNX_OFED or inbox)
- Load required modules: `modprobe rdma_ucm && modprobe ib_uverbs`
- Update firmware: `mlxfwmanager --online -u`
- Check kernel compatibility

### Firmware Errors
**Symptoms:**
- Device shows but operations fail
- `dmesg` shows firmware command errors
- Health monitoring events

**Diagnosis:**
```bash
mst status
mlxfwmanager --query
dmesg | grep -i "firmware\|health\|fatal"
cat /sys/class/infiniband/*/fw_ver
```

**Fixes:**
- Update firmware to latest recommended version
- Reset device: `mlxfwreset -d <dev> reset`
- Cold reboot if warm reset insufficient

---

## 7. Counter Reference

### Key Performance Counters
| Counter | Location | Meaning |
|---------|----------|---------|
| `port_xmit_data` | sysfs counters | Total transmitted data |
| `port_rcv_data` | sysfs counters | Total received data |
| `port_xmit_packets` | sysfs counters | Total transmitted packets |
| `port_rcv_packets` | sysfs counters | Total received packets |

### Key Error Counters
| Counter | Location | Meaning |
|---------|----------|---------|
| `port_rcv_errors` | sysfs counters | Receive errors (bad packets) |
| `port_xmit_discards` | sysfs counters | Transmit discards |
| `symbol_error` | sysfs counters | Physical layer symbol errors |
| `link_error_recovery` | sysfs counters | Link error recovery events |
| `link_downed` | sysfs counters | Link down events |
| `local_link_integrity_errors` | sysfs counters | Local link integrity issues |
| `excessive_buffer_overrun_errors` | sysfs counters | Buffer overflows |
| `port_rcv_remote_physical_errors` | sysfs counters | Remote physical errors (RNR) |
