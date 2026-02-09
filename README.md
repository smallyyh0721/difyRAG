# RDMA RAG + Agent System (Dify-based)

An automated RDMA monitoring, diagnosis, and remediation system built on the [Dify](https://dify.ai) platform. Uses RAG (Retrieval-Augmented Generation) with a curated RDMA knowledge base to provide context-aware troubleshooting and automated fixes.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Linux Server                             │
│  ┌──────────────┐     ┌──────────────────────────────────────┐  │
│  │ RDMA Monitor │────▶│  RDMA Log Collector                  │  │
│  │   Daemon     │     │  (ibstat, counters, dmesg, sysfs)    │  │
│  └──────┬───────┘     └──────────────────────────────────────┘  │
│         │ JSON snapshot                                         │
│  ┌──────▼───────┐                                               │
│  │ Agent Tools  │◀──── Dify calls tools to execute fixes        │
│  │ API (Flask)  │                                               │
│  └──────────────┘                                               │
└─────────┬───────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Dify Platform                              │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Workflow 1: Auto-Monitor                               │    │
│  │  Snapshot → LLM Analysis → RAG Query → Action Plan      │    │
│  │  → Agent Execute → Verify → Alarm (if needed)           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Workflow 2: Q&A Chatbot                                │    │
│  │  User Query → Classify → RAG (if RDMA) → Answer         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌──────────────┐  ┌──────────┐  ┌─────────┐  ┌──────────┐    │
│  │  Local LLM   │  │ Embedding│  │ Rerank  │  │  Qdrant  │    │
│  │  (OpenAI API)│  │  Model   │  │  Model  │  │  Vector  │    │
│  └──────────────┘  └──────────┘  └─────────┘  │    DB    │    │
│                                                └──────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
difyRAG/
├── config/                          # Configuration files
│   ├── dify.env.example             # Environment variables template
│   ├── monitor.conf.example         # Monitor daemon config template
│   └── dify_model_provider_setup.md # Step-by-step Dify model setup
├── knowledge_base/                  # RAG knowledge documents
│   ├── rdma_docs/
│   │   └── rdma_fundamentals.md     # RDMA concepts, protocols, stack
│   └── troubleshooting/
│       ├── rdma_common_issues.md    # Issue diagnosis & fixes
│       └── rdma_action_plans.md     # Structured action plans for agent
├── collector/                       # Data collection
│   ├── rdma_log_collector.sh        # Collects RDMA state as JSON
│   └── rdma_monitor_daemon.sh       # Periodic health check daemon
├── agent_tools/                     # Dify custom tools (API)
│   ├── rdma_tools.py                # Flask API with all agent tools
│   └── requirements.txt             # Python dependencies
├── dify_workflows/                  # Dify workflow definitions
│   ├── rdma_monitor_workflow.yml    # Workflow 1: Auto-monitor
│   └── rdma_qa_chatbot.yml          # Workflow 2: Q&A chatbot
├── scripts/                         # Operational scripts
│   ├── start_tools_service.sh       # Start agent tools API
│   └── start_monitor.sh             # Start monitor daemon
└── README.md
```

## Prerequisites

- **Dify** instance deployed and accessible
- **Local LLM** deployed with OpenAI-compatible API
- **Embedding model** deployed with OpenAI-compatible API
- **Rerank model** deployed with OpenAI-compatible API
- **Qdrant** vector database running
- **Python 3.10+** on the monitored Linux server
- RDMA-capable hardware (InfiniBand or RoCE NIC)

## Setup

### 1. Configure Environment

```bash
cp config/dify.env.example config/.env
# Edit config/.env with your actual endpoints and API keys
```

### 2. Set Up Models in Dify

Follow the step-by-step guide in `config/dify_model_provider_setup.md` to:
- Add your local LLM as an OpenAI-compatible model provider
- Add your embedding model
- Add your rerank model
- Configure Qdrant as the vector store

### 3. Create Knowledge Base in Dify

1. Go to Dify → Knowledge → Create Knowledge
2. Upload all files from the `knowledge_base/` directory
3. Set indexing mode to **High Quality**
4. Select your embedding model
5. Configure chunk size: 800-1000 tokens, overlap: 100-150 tokens
6. Enable reranking with your rerank model

### 4. Create Workflows in Dify

Use the YAML blueprints in `dify_workflows/` as reference to build:

**Workflow 1 - Auto-Monitor** (`rdma_monitor_workflow.yml`):
1. Create a new Workflow-type application
2. Add nodes as described in the YAML
3. Connect to the knowledge base created above
4. Add the agent tools as custom tools (import OpenAPI schema from `http://<tools-host>:5100/openapi.json`)

**Workflow 2 - Q&A Chatbot** (`rdma_qa_chatbot.yml`):
1. Create a new Chatbot-type application
2. Configure the pre-prompt as shown in the YAML
3. Connect to the same knowledge base
4. Optionally enable agent mode with the diagnostic tools

### 5. Deploy Agent Tools Service

```bash
cd agent_tools
pip install -r requirements.txt
cd ..
chmod +x scripts/*.sh collector/*.sh
./scripts/start_tools_service.sh
```

The tools API will be available at `http://<host>:5100`. Import the OpenAPI schema into Dify:
- Go to Dify → Tools → Custom → Create Custom Tool
- Enter `http://<host>:5100/openapi.json`

### 6. Start the Monitor Daemon

```bash
cp config/monitor.conf.example config/monitor.conf
# Edit config/monitor.conf with your Dify API details
./scripts/start_monitor.sh
```

## Two Workflows

### Workflow 1: Automatic RDMA Monitoring

```
Monitor Daemon (cron/loop)
  ├── Health check (port state, error counters)
  ├── If issues detected:
  │   ├── Collect full snapshot (JSON)
  │   ├── Send to Dify Workflow API
  │   │   ├── LLM analyzes snapshot
  │   │   ├── RAG retrieves relevant knowledge
  │   │   ├── LLM generates action plan
  │   │   ├── Agent executes fix steps
  │   │   ├── LLM verifies result
  │   │   └── If fix failed → alarm human
  │   └── Log result
  └── If healthy: log OK, sleep, repeat
```

### Workflow 2: Interactive Q&A

```
User asks question
  ├── LLM classifies: RDMA-related or general?
  ├── If RDMA-related:
  │   ├── Query RAG knowledge base
  │   ├── Rerank results
  │   └── LLM answers with RAG context
  └── If general:
      └── LLM answers directly
```

## Agent Tools

| Tool | Description |
|------|-------------|
| `rdma_check_status` | Check RDMA device and port status |
| `rdma_check_counters` | Read error and performance counters |
| `rdma_reset_port` | Reset RDMA port (IB or RoCE) |
| `rdma_reload_driver` | Reload RDMA kernel modules |
| `rdma_configure_qos` | Configure RoCE PFC/ECN settings |
| `rdma_set_memlock` | Set memory lock limits |
| `rdma_run_perftest` | Run RDMA performance benchmarks |
| `rdma_check_pcie` | Check PCIe link configuration |
| `send_alarm` | Alert human operators |

## Adding Knowledge

To expand the RAG knowledge base:

1. Add new `.md` files to `knowledge_base/` covering:
   - Vendor-specific guides (Mellanox/NVIDIA, Intel)
   - Your organization's RDMA configurations
   - Past incident reports and resolutions
   - Performance baselines for your hardware
2. Upload to Dify Knowledge and re-index

## Safety

- The agent tools service has a **DRY_RUN** mode for testing
- Destructive operations (driver reload, port reset) are logged
- The escalation path ensures humans are alerted when automation fails
- API key authentication protects the tools endpoint
