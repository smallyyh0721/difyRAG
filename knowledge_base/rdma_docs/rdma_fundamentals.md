# RDMA Fundamentals Knowledge Base

## What is RDMA

Remote Direct Memory Access (RDMA) allows direct memory access from one computer to another without involving the operating system of either machine. It enables high-throughput, low-latency networking, which is especially useful in massively parallel computing environments.

## RDMA Protocols

### InfiniBand (IB)
- Native RDMA protocol
- Requires specialized InfiniBand network adapters (HCAs) and switches
- Provides highest performance with lowest latency
- Common in HPC clusters and AI/ML training environments

### RDMA over Converged Ethernet (RoCE)
- **RoCE v1**: RDMA over Ethernet (Layer 2 only)
- **RoCE v2**: RDMA over UDP/IP (Layer 3 routable)
- Uses standard Ethernet infrastructure with RDMA-capable NICs
- Requires lossless Ethernet configuration (PFC/ECN)

### iWARP (Internet Wide Area RDMA Protocol)
- RDMA over TCP/IP
- Works over standard Ethernet without lossless requirements
- Higher latency than InfiniBand and RoCE
- Simpler deployment

## Key RDMA Concepts

### Queue Pairs (QP)
- Each RDMA connection uses a Queue Pair
- Send Queue (SQ) + Receive Queue (RQ) = Queue Pair
- QP states: RESET → INIT → RTR → RTS → ERROR
- QP types: RC (Reliable Connected), UC (Unreliable Connected), UD (Unreliable Datagram)

### Completion Queues (CQ)
- Used to notify when RDMA operations complete
- Each WQE completion generates a CQE (Completion Queue Entry)
- CQE contains status (success/error) and operation details

### Memory Registration (MR)
- Memory must be registered before RDMA operations
- Registration pins pages in physical memory
- Returns local key (lkey) and remote key (rkey)
- Deregistration must happen before freeing memory

### Protection Domain (PD)
- Security mechanism for RDMA resources
- QPs and MRs must belong to same PD to interact
- Prevents unauthorized access between processes

## RDMA Operations

### One-sided operations (no remote CPU involvement)
- **RDMA Read**: Read data from remote memory
- **RDMA Write**: Write data to remote memory
- **RDMA Atomic**: Compare-and-swap, fetch-and-add

### Two-sided operations
- **Send/Receive**: Traditional message passing with remote CPU notification

## Linux RDMA Stack

### Kernel Components
- `ib_core`: Core RDMA abstractions
- `ib_uverbs`: User-space verbs interface
- `rdma_cm`: RDMA connection manager
- `mlx5_ib`, `mlx4_ib`: Mellanox/NVIDIA device drivers
- `rxe`: Soft-RoCE (software RDMA over Ethernet)

### User-space Components
- `libibverbs`: Core verbs library
- `librdmacm`: Connection management library
- `libmlx5`, `libmlx4`: Device-specific user-space drivers
- `rdma-core`: Unified RDMA user-space package

### Key Configuration Files
- `/etc/rdma/rdma.conf`: RDMA subsystem configuration
- `/etc/rdma/modules/`: Module loading configuration
- `/sys/class/infiniband/`: Sysfs interface for RDMA devices
- `/sys/class/net/<dev>/`: Network device attributes

### Important Commands
- `ibstat`: Show InfiniBand device status
- `ibstatus`: Show InfiniBand port status
- `ibv_devinfo`: Show RDMA device information
- `rdma`: iproute2 RDMA configuration tool
- `perftest` tools: `ib_write_bw`, `ib_read_lat`, etc.
- `ibdiagnet`: InfiniBand diagnostic tool
