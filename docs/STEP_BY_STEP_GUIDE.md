# Complete Step-by-Step Setup Guide

---

## Phase 1: Deploy Dify

```bash
cd /path/to/difyRAG
./scripts/deploy_dify.sh
```

Wait ~2 minutes. Open browser: **http://localhost/install**

1. Set admin email: `admin@example.com`
2. Set password: `dify123456`
3. Click **"Setup"**

---

## Phase 2: Add Your Models (3 models)

Go to **top-right avatar icon → Settings → Model Providers**

### 2.1 Add Local LLM

1. Scroll down, find **"OpenAI-API-compatible"**, click it
2. Click **"Add Model"**
3. Fill in:
   - **Model Type**: `LLM`
   - **Model Name**: your model name (e.g. `qwen2.5-72b`)
   - **API Key**: your key (or any placeholder if your endpoint doesn't check)
   - **API Endpoint URL**: `http://<your-llm-host>:<port>/v1`
   - **Completion mode**: `Chat`
   - **Model context size**: e.g. `32768`
   - **Upper bound for max tokens**: e.g. `4096`
4. Click **"Save"** → green check = success

### 2.2 Add Embedding Model

1. Click **"Add Model"** again in OpenAI-API-compatible
2. Fill in:
   - **Model Type**: `Text Embedding`
   - **Model Name**: e.g. `bge-large-en-v1.5`
   - **API Key**: your key
   - **API Endpoint URL**: `http://<embedding-host>:<port>/v1`
3. Click **"Save"**

### 2.3 Add Rerank Model

1. Click **"Add Model"** again
2. Fill in:
   - **Model Type**: `Rerank`
   - **Model Name**: e.g. `bge-reranker-v2-m3`
   - **API Key**: your key
   - **API Endpoint URL**: `http://<rerank-host>:<port>/v1`
3. Click **"Save"**

### 2.4 Set Default System Model

1. In Settings, click **"System Model Settings"** tab at the top
2. Set **System Reasoning Model** → your LLM
3. Set **Embedding Model** → your embedding model
4. Click **"Save"**

---

## Phase 3: Create Knowledge Base (RAG)

1. Click **"Knowledge"** in the left sidebar
2. Click **"Create Knowledge"**
3. Name: `RDMA Knowledge Base`
4. Click **"Import from file"**
5. Upload these 3 files from `knowledge_base/`:
   - `rdma_docs/rdma_fundamentals.md`
   - `troubleshooting/rdma_common_issues.md`
   - `troubleshooting/rdma_action_plans.md`
6. Click **"Next"**
7. Configure indexing:
   - Indexing mode: **High Quality**
   - Chunk length: **800**, Overlap: **100**
   - Embedding Model: select yours
   - Retrieval: **Semantic Search**, Top K: **5**, Score threshold: **0.5**
   - Reranking: enable, select your rerank model, Top N: **3**
8. Click **"Save & Process"** → wait for indexing to complete

---

## Phase 4: Start Agent Tools Service

```bash
cd /path/to/difyRAG/agent_tools
pip install -r requirements.txt
python rdma_tools.py
```

Verify it works:
```bash
curl http://localhost:5100/openapi.json
# Should return JSON schema
```

Leave this running (use `nohup` or `screen` for background).

---

## Phase 5: Import Workflows into Dify

Dify supports importing workflows from YAML DSL files. We provide two
ready-to-import files. You just need to edit a few placeholder values.

### 5.1 Prepare DSL Files

Before importing, edit the DSL files to replace placeholders with your actual values.

**File 1**: `dify_workflows/rdma_monitor_workflow.dsl.yml`

**File 2**: `dify_workflows/rdma_qa_chatbot.dsl.yml`

In **both** files, find-and-replace these placeholders:

| Placeholder | Replace With | Example |
|---|---|---|
| `PUT_YOUR_MODEL_NAME_HERE` | Your LLM model name | `qwen2.5-72b` |
| `YOUR_SERVER_IP` | Your agent tools server IP | `192.168.1.100` |

```bash
# Quick way to do it:
cd dify_workflows

# Replace model name in both files
sed -i 's/PUT_YOUR_MODEL_NAME_HERE/qwen2.5-72b/g' rdma_monitor_workflow.dsl.yml
sed -i 's/PUT_YOUR_MODEL_NAME_HERE/qwen2.5-72b/g' rdma_qa_chatbot.dsl.yml

# Replace server IP (only in monitor workflow)
sed -i 's/YOUR_SERVER_IP/192.168.1.100/g' rdma_monitor_workflow.dsl.yml
```

### 5.2 Import Workflow 1: Auto-Monitor

1. Go to **"Studio"** in Dify left sidebar
2. Click the **down-arrow ▼** next to "Create from Blank" → click **"Import DSL File"**
3. Select file: `dify_workflows/rdma_monitor_workflow.dsl.yml`
4. Click **"Create"**
5. The workflow opens with all nodes already connected:

```
Start
  │
  ▼
LLM: Analyze RDMA Snapshot
  │
  ▼
IF/ELSE: Issues Found?
  │(yes)              │(no)
  ▼                   ▼
Knowledge          End - Healthy
Retrieval
  │
  ▼
LLM: Generate Action Plan
  │
  ▼
HTTP: Execute Action Plan ──────── calls http://<ip>:5100/tools/rdma_action_executor
  │
  ▼
LLM: Verify Fix Result
  │
  ▼
IF/ELSE: Needs Escalation?
  │(yes)              │(no)
  ▼                   ▼
HTTP: Send Alarm   End - Fixed
  │
  ▼
End - Escalated
```

### 5.3 Fix Up After Import: Knowledge Base

The Knowledge Retrieval node needs your Knowledge Base linked:

1. Click the **"Query RDMA Knowledge Base"** node on the canvas
2. In the right panel, click **"Knowledge"** (the dataset selector, shows empty)
3. Click **"+"** → check **"RDMA Knowledge Base"** → click **"Add"**
4. Under **Rerank Model**: select your rerank model
5. That's it, the node is now connected to your RAG data

### 5.4 Fix Up After Import: Verify HTTP URLs

1. Click the **"Execute Action Plan"** node
2. Check the **URL** field shows: `http://<your-ip>:5100/tools/rdma_action_executor`
   - If Dify is in Docker on the same machine, use your machine's LAN IP, **not** `localhost`
3. Click the **"Send Alarm"** node
4. Check its URL: `http://<your-ip>:5100/tools/send_alarm`

### 5.5 Test the Workflow

1. Click **"Run"** button (top right, the ▶ play icon)
2. Fill in the test inputs:

   **rdma_snapshot**:
   ```json
   {"hostname":"rdma-server-01","ibstat":"CA 'mlx5_0'\n  Port 1:\n    State: Down\n    Physical state: Polling\n    Rate: 100","dmesg_rdma":"[12345.678] mlx5_core 0000:86:00.0: Port 1: link down","port_counters":"symbol_error: 150\nlink_downed: 3\nport_rcv_errors: 0","loaded_modules":"mlx5_core 1234567 1 mlx5_ib","pci_devices":"86:00.0 Infiniband controller: Mellanox ConnectX-6"}
   ```

   **health_status**:
   ```
   PORT_NOT_ACTIVE:mlx5_0/ports/1;ERROR_COUNTER:mlx5_0/ports/1/symbol_error=150
   ```

3. Click **"Run"**
4. Watch each node execute in sequence -- click any node to see its output
5. The flow should go: Start → Analyze → IF(yes) → RAG → Action Plan → HTTP Execute → Verify → IF → End

### 5.6 Publish and Get API Key

1. Click **"Publish"** (top right)
2. Click **"Access API"** (appears after publish)
3. On the API page, click **"API Key"** → **"Create"** → copy the key
4. Your endpoint: `http://localhost/v1/workflows/run`
5. Save this API key -- the monitor daemon needs it

---

### 5.7 Import Workflow 2: Q&A Chatbot

1. Go back to **"Studio"**
2. Click **▼** → **"Import DSL File"**
3. Select: `dify_workflows/rdma_qa_chatbot.dsl.yml`
4. Click **"Create"**
5. The chatflow opens:

```
Start
  │
  ▼
LLM: Classify Question  ──── "rdma" or "general"?
  │
  ▼
IF/ELSE: RDMA Related?
  │(yes)                │(no)
  ▼                     ▼
Knowledge            LLM: Direct Answer
Retrieval               │
  │                     ▼
  ▼                  Answer (General)
LLM: Answer with
Knowledge Base
  │
  ▼
Answer (RDMA)
```

### 5.8 Fix Up the Q&A Chatbot

Same as before:
1. Click **"Search RDMA Knowledge Base"** node → add your **RDMA Knowledge Base** + rerank model
2. Click **"Publish"**

### 5.9 Test the Chatbot

1. Click **"Run"** (▶ button, top right) -- opens the chat preview
2. Test RDMA questions:
   - `How do I check if my RDMA port is active?` → should use RAG, gives ibstat commands
   - `What causes RNR retry exceeded errors?` → should use RAG, detailed explanation
   - `How do I configure PFC for RoCE?` → should use RAG, gives mlnx_qos commands
3. Test general questions:
   - `What is Python?` → should answer directly, no RAG
   - `What is 2+2?` → should answer directly
4. You can see which path was taken by watching node highlights in real-time

---

## Phase 6: HTTP Request Node -- Detailed Explanation

This is the node that calls your agent tools. Here's exactly how each field is set:

### Execute Action Plan Node

| Field | Value |
|---|---|
| **Method** | `POST` |
| **URL** | `http://<your-server-ip>:5100/tools/rdma_action_executor` |
| **Headers** | Key: `Content-Type`, Value: `application/json` |
| **Body Type** | `JSON` |
| **Body Data** | Key: `action_plan`, Type: `text`, Value: click `{x}` → select `node_action_plan` → `text` |
| **Timeout - Read** | `120` (action execution can take time) |

The body sends the LLM-generated action plan JSON to the executor, which parses
the plan and runs each tool step in sequence.

### Send Alarm Node

| Field | Value |
|---|---|
| **Method** | `POST` |
| **URL** | `http://<your-server-ip>:5100/tools/send_alarm` |
| **Headers** | Key: `Content-Type`, Value: `application/json` |
| **Body Type** | `JSON` |
| **Body Data** | 3 keys: |
| | `severity` = `critical` (plain text) |
| | `summary` = click `{x}` → select `node_verify` → `text` |
| | `details` = click `{x}` → select `node_analyze` → `text` |

### How to Reference Variables in Body

In the Body JSON editor:
1. Each row has: **Key**, **Type**, **Value**
2. For **Type**: choose `text`
3. For **Value**: click the **`/`** or **`{x}`** icon in the value field
4. A dropdown appears showing available upstream nodes
5. Select the node (e.g. `Generate Action Plan`) → select its output (e.g. `text`)
6. Dify inserts: `{{#node_action_plan.text#}}`

### Important: Docker Networking

Since Dify API runs inside Docker:
- **`localhost`** inside Docker = the Docker container itself, NOT your host machine
- Use your machine's **LAN IP** instead (e.g. `192.168.1.100`)
- Or use `host.docker.internal` (works on Docker Desktop)

To find your LAN IP:
```bash
hostname -I | awk '{print $1}'
```

---

## Phase 7: Start the Monitor Daemon

### 7.1 Configure

```bash
cp config/monitor.conf.example config/monitor.conf
```

Edit `config/monitor.conf`:
```bash
DIFY_API_URL=http://localhost/v1/workflows/run
DIFY_API_KEY=app-xxxxxxxxxxxxxxxxxxxx    # from Phase 5.6
CHECK_INTERVAL=60
```

### 7.2 Start

```bash
# Foreground (see logs directly)
./scripts/start_monitor.sh

# Background
nohup ./scripts/start_monitor.sh &
```

Logs are written to `./logs/` inside the project directory (no sudo needed).

---

## Phase 8: Verify End-to-End

### Test Agent Tools
```bash
curl -s -X POST http://localhost:5100/tools/rdma_check_status | python3 -m json.tool
curl -s -X POST http://localhost:5100/tools/rdma_check_pcie | python3 -m json.tool
```

### Test Workflow via API
```bash
curl -X POST http://localhost/v1/workflows/run \
  -H "Authorization: Bearer app-YOUR_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "rdma_snapshot": "{\"hostname\":\"test\",\"ibstat\":\"Port 1: State: Down\",\"dmesg_rdma\":\"link down\",\"port_counters\":\"symbol_error: 50\"}",
      "health_status": "PORT_NOT_ACTIVE:mlx5_0/ports/1",
      "mode": "manual_trigger"
    },
    "response_mode": "blocking",
    "user": "test-user"
  }'
```

### Test Chatbot via API
```bash
curl -X POST http://localhost/v1/chat-messages \
  -H "Authorization: Bearer app-YOUR_CHATBOT_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {},
    "query": "How do I check if my RDMA port is active?",
    "response_mode": "blocking",
    "user": "test-user"
  }'
```

---

## Quick Reference: Ports

| Service | Port | Purpose |
|---------|------|---------|
| Dify Web UI | 80 | Main interface |
| Dify API | 80 (/v1) | Workflow/chatbot API |
| Agent Tools | 5100 | RDMA tool endpoints |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "Model not found" in workflow | Settings → Model Providers → verify green check |
| Knowledge Retrieval returns nothing | Knowledge page → verify indexing done, lower threshold to 0.3 |
| HTTP Request node timeout | Check agent tools running, use LAN IP not localhost |
| Monitor daemon permission denied | Logs default to `./logs/`, no sudo needed |
| DSL import fails | Check Dify version matches, ensure YAML is valid |
