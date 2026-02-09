# Complete Step-by-Step Setup Guide

This guide walks you through the entire system setup with exact click-by-click instructions.

---

## Phase 1: Deploy Dify

```bash
cd /path/to/difyRAG
./scripts/deploy_dify.sh
```

Wait ~2 minutes. Open browser: **http://localhost/install**

1. Set admin email: `admin@example.com`
2. Set password: `dify123456` (pre-filled if deploy script ran)
3. Click **"Setup"**
4. You are now in the Dify dashboard

---

## Phase 2: Add Your Models (3 models to add)

Go to **top-right avatar → Settings → Model Providers**

### 2.1 Add Local LLM

1. Scroll down to **"OpenAI-API-compatible"** provider, click it
2. Click **"Add Model"**
3. Fill in:
   - **Model Type**: `LLM`
   - **Model Name**: your model name (e.g., `qwen2.5-72b`, `llama3-70b`, whatever you deployed)
   - **API Key**: your LLM API key (or any placeholder if your endpoint doesn't check)
   - **API Endpoint URL**: `http://<your-llm-host>:<port>/v1`
     - Example: `http://192.168.1.100:8000/v1`
   - **Completion mode**: `Chat` (most models use chat)
   - **Model context size**: set to your model's max (e.g., `32768`)
   - **Upper bound for max tokens**: set to your model's max output (e.g., `4096`)
   - Leave other fields default
4. Click **"Save"**
5. Dify will test the connection -- green check = success

### 2.2 Add Embedding Model

1. Still in **OpenAI-API-compatible**, click **"Add Model"** again
2. Fill in:
   - **Model Type**: `Text Embedding`
   - **Model Name**: your embedding model name (e.g., `bge-large-en-v1.5`)
   - **API Key**: your embedding API key
   - **API Endpoint URL**: `http://<your-embedding-host>:<port>/v1`
3. Click **"Save"**

### 2.3 Add Rerank Model

1. Click **"Add Model"** again
2. Fill in:
   - **Model Type**: `Rerank`
   - **Model Name**: your rerank model name (e.g., `bge-reranker-v2-m3`)
   - **API Key**: your rerank API key
   - **API Endpoint URL**: `http://<your-rerank-host>:<port>/v1`
3. Click **"Save"**

### 2.4 Set Default Model

1. Still in Settings, click **"System Model Settings"** tab (at top)
2. Set **System Reasoning Model** → select your LLM
3. Set **Embedding Model** → select your embedding model
4. Click **"Save"**

---

## Phase 3: Create Knowledge Base (RAG)

### 3.1 Create and Upload

1. Click **"Knowledge"** in the left sidebar
2. Click **"Create Knowledge"** button
3. Name it: `RDMA Knowledge Base`
4. Click **"Import from file"**
5. Upload these 3 files from the `knowledge_base/` directory:
   - `rdma_docs/rdma_fundamentals.md`
   - `troubleshooting/rdma_common_issues.md`
   - `troubleshooting/rdma_action_plans.md`
6. Click **"Next"**

### 3.2 Configure Indexing

On the indexing settings page:

1. **Chunk Settings**:
   - Indexing mode: **High Quality**
   - Chunk length: **800**
   - Chunk overlap: **100**
2. **Embedding Model**: Select your embedding model (added in step 2.2)
3. **Retrieval Setting**:
   - Click **"Semantic Search"**
   - Top K: **5**
   - Score threshold: enable, set to **0.5**
   - Reranking model: select your rerank model (added in step 2.3)
   - Top N after reranking: **3**
4. Click **"Save & Process"**
5. Wait for indexing to complete (progress bar shown)

### 3.3 Note the Knowledge Base ID

After creation, look at the browser URL:
```
http://localhost/datasets/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/documents
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                          This is your Knowledge Base ID
```
Copy this ID -- you'll need it for API calls from the monitor daemon.

---

## Phase 4: Start Agent Tools Service

On the RDMA-monitored server (can be same machine):

```bash
cd /path/to/difyRAG/agent_tools
pip install -r requirements.txt
python rdma_tools.py
```

This starts the tools API on **port 5100**. Verify:
```bash
curl http://localhost:5100/openapi.json
```
You should see the OpenAPI schema JSON.

---

## Phase 5: Import Agent Tools into Dify

### 5.1 Create Custom Tool

1. In Dify, go to **"Tools"** in the left sidebar
2. Click **"Custom Tool"** → **"Create Custom Tool"**
3. Fill in:
   - **Name**: `RDMA Agent Tools`
   - **Schema**: Click **"Import from URL"**
   - Enter URL: `http://<tools-server-ip>:5100/openapi.json`
     - If Dify and tools are on the same machine: `http://host.docker.internal:5100/openapi.json`
     - Or use your machine's LAN IP: `http://192.168.x.x:5100/openapi.json`
   - The schema will auto-populate with all 9 tools
4. **Available Tools** section will show:
   - rdma_check_status
   - rdma_check_counters
   - rdma_reset_port
   - rdma_reload_driver
   - rdma_configure_qos
   - rdma_set_memlock
   - rdma_run_perftest
   - rdma_check_pcie
   - send_alarm
5. Click **"Save"**
6. Test any tool by clicking the **"Test"** button next to it

> **Note on Docker networking**: Since Dify runs inside Docker, `localhost` inside Docker
> is NOT your host machine. Use `host.docker.internal` (Docker Desktop) or your machine's
> actual IP address instead.

---

## Phase 6: Build Workflow 1 -- RDMA Auto-Monitor

### 6.1 Create the Application

1. Go to **"Studio"** (left sidebar)
2. Click **"Create from Blank"**
3. Select **"Workflow"**
4. Name: `RDMA Auto-Monitor & Action Agent`
5. Click **"Create"**

### 6.2 Add Input Variables (Start Node)

Click the **Start** node on the canvas:

1. Click **"+"** under Input to add variables:
   - Variable 1: `rdma_snapshot` (type: Paragraph, required: yes)
   - Variable 2: `health_status` (type: Short Text, required: yes)
   - Variable 3: `mode` (type: Short Text, default: `auto_monitor`)

### 6.3 Add Node: Analyze Issues (LLM)

1. Click **"+"** after the Start node → select **"LLM"**
2. Title: `Analyze RDMA Snapshot`
3. Select your LLM model
4. System prompt -- paste this:

```
You are an RDMA networking expert. Analyze the following RDMA system snapshot and identify any issues, errors, or anomalies.

Health Status: {{#1719284746.health_status#}}

Full System Snapshot:
{{#1719284746.rdma_snapshot#}}

Provide your analysis in this JSON format:
{
  "has_issues": true/false,
  "severity": "critical/warning/info",
  "issues": [
    {
      "category": "link|performance|connection|memory|driver|config",
      "description": "Brief description of the issue",
      "evidence": "Specific data from the snapshot",
      "keywords": "search keywords for RAG lookup"
    }
  ],
  "summary": "One-paragraph summary"
}
```

> **Important**: The `{{#1719284746.xxx#}}` syntax is Dify's variable reference. In the
> prompt editor, click the **`{x}`** button and select the Start node variables instead
> of typing these manually. Dify will auto-generate the correct reference IDs.

### 6.4 Add Node: IF/ELSE (Issues Found?)

1. Click **"+"** → select **"IF/ELSE"**
2. Title: `Issues Found?`
3. Condition: `Analyze RDMA Snapshot` output → **contains** → `"has_issues": true`

### 6.5 Add Node: Knowledge Retrieval (IF branch)

1. On the **IF (true)** branch, click **"+"** → select **"Knowledge Retrieval"**
2. Title: `Query RDMA Knowledge Base`
3. **Knowledge**: Click and select `RDMA Knowledge Base` (created in Phase 3)
4. **Query variable**: Click `{x}` → select the LLM output from step 6.3
   (You can also use a Code node to extract the `keywords` field first)
5. **Retrieval settings**:
   - Semantic Search
   - Top K: 5
   - Reranking: enable, select your rerank model, Top N: 3

### 6.6 Add Node: Generate Action Plan (LLM)

1. Click **"+"** → select **"LLM"**
2. Title: `Generate Action Plan`
3. Paste the prompt from `rdma_monitor_workflow.yml` lines 116-152
4. Use `{x}` button to reference:
   - Analysis result from node 6.3
   - RAG results from node 6.5

### 6.7 Add Node: Execute Action (HTTP Request)

Since Dify workflows can't directly call custom tools in sequence, use HTTP Request:

1. Click **"+"** → select **"HTTP Request"**
2. Title: `Execute Action Plan`
3. Configure:
   - Method: **POST**
   - URL: `http://<tools-server-ip>:5100/tools/rdma_action_executor`
   - Headers: `Content-Type: application/json`
   - Body (JSON): `{"action_plan": {{#action_plan_variable#}}}`
     (reference the LLM output from step 6.6)

### 6.8 Add Node: Verify Fix (LLM)

1. Click **"+"** → select **"LLM"**
2. Title: `Verify Fix Result`
3. Paste the prompt from `rdma_monitor_workflow.yml` lines 177-201
4. Reference all prior outputs

### 6.9 Add Node: IF/ELSE (Needs Escalation?)

1. Click **"+"** → select **"IF/ELSE"**
2. Condition: Verify output → **contains** → `"needs_escalation": true`
3. IF true → add **HTTP Request** node to call `send_alarm` tool
4. IF false → connect to **End** node

### 6.10 Add End Nodes

Add 3 End nodes and connect them:
- **End (Healthy)**: from the ELSE branch of step 6.4
- **End (Fixed)**: from the ELSE branch of step 6.9
- **End (Escalated)**: from the IF branch of step 6.9 (after alarm)

### 6.11 The Final Flow Looks Like:

```
Start
  │
  ▼
LLM: Analyze Snapshot
  │
  ▼
IF/ELSE: Issues Found?
  │              │
  │(yes)         │(no)
  ▼              ▼
Knowledge    End(Healthy)
Retrieval
  │
  ▼
LLM: Generate Action Plan
  │
  ▼
HTTP: Execute Actions
  │
  ▼
LLM: Verify Fix
  │
  ▼
IF/ELSE: Needs Escalation?
  │              │
  │(yes)         │(no)
  ▼              ▼
HTTP: Alarm   End(Fixed)
  │
  ▼
End(Escalated)
```

### 6.12 Publish and Get API Key

1. Click **"Publish"** (top right)
2. Click **"Access API"** → shows the API endpoint
3. Click **"API Key"** → **"Create"** → copy the key
4. Your workflow API endpoint is: `http://localhost/v1/workflows/run`
5. Save this key -- the monitor daemon needs it

---

## Phase 7: Build Workflow 2 -- RDMA Q&A Chatbot

### 7.1 Create the Application

1. Go to **"Studio"** → **"Create from Blank"**
2. Select **"Chatbot"**
3. Select **"Chatflow"** (orchestrate mode)
4. Name: `RDMA Knowledge Assistant`
5. Click **"Create"**

### 7.2 Configure the Chatflow

1. In the **Start** node, the user's message is automatically the input

2. Add **LLM** node: `Classify Question`
   - Prompt:
   ```
   Classify the following user question. Is it related to RDMA, InfiniBand,
   RoCE, iWARP, high-performance networking, or network troubleshooting
   on Linux servers?

   User question: {{#sys.query#}}

   Respond with ONLY one word: "rdma" or "general"
   ```

3. Add **IF/ELSE** node: `RDMA Related?`
   - Condition: Classify output → contains → `rdma`

4. **IF (yes)** branch:
   - Add **Knowledge Retrieval** node
     - Select `RDMA Knowledge Base`
     - Query: `{{#sys.query#}}`
     - Semantic search, Top K: 5, reranking enabled
   - Add **LLM** node: `Answer with Knowledge Base`
     - Prompt:
     ```
     Answer the user's RDMA-related question using the knowledge base context.

     ## Knowledge Base Context
     {{#knowledge_retrieval_output#}}

     ## User Question
     {{#sys.query#}}

     Provide a clear, practical answer with commands and examples.
     ```
   - Connect to **Answer** node (End)

5. **ELSE (no)** branch:
   - Add **LLM** node: `Direct Answer`
     - Prompt: `Answer this general question: {{#sys.query#}}`
   - Connect to **Answer** node (End)

### 7.3 Alternative: Simple Chatbot (Easier)

If the Chatflow feels complex, use the simpler approach:

1. Create **"Chatbot"** → **"Basic"** (not Chatflow)
2. Set the **System Prompt** (Instructions):
```
You are an expert RDMA networking assistant. Help users with RDMA concepts,
troubleshooting, performance tuning, and configuration on Linux systems.
Always provide practical commands and examples.
```
3. Enable **Knowledge Base**:
   - Click **"Context"** → **"Add"** → select `RDMA Knowledge Base`
4. Enable **Tools** (optional):
   - Click **"Tools"** → **"Add Tool"** → select your RDMA custom tools
5. Click **"Publish"**

This simpler version uses Dify's built-in RAG integration -- it automatically
queries the knowledge base for every user message and passes context to the LLM.

---

## Phase 8: Start the Monitor Daemon

### 8.1 Configure the Daemon

```bash
cp config/monitor.conf.example config/monitor.conf
```

Edit `config/monitor.conf`:
```bash
# Use the API key from Phase 6 step 6.12
DIFY_API_URL=http://localhost/v1/workflows/run
DIFY_API_KEY=app-xxxxxxxxxxxxxxxxxxxx

# Check every 60 seconds
CHECK_INTERVAL=60

RDMA_LOG_DIR=/var/log/rdma_collector
```

### 8.2 Start the Daemon

```bash
sudo mkdir -p /var/log/rdma_collector
./scripts/start_monitor.sh
```

Or run in background:
```bash
nohup ./scripts/start_monitor.sh &> /var/log/rdma_collector/monitor.log &
```

### 8.3 What Happens Now

Every 60 seconds:
1. Daemon checks RDMA port states and error counters
2. If issues detected → runs `rdma_log_collector.sh` to get full JSON snapshot
3. Sends snapshot to Dify workflow via API
4. Dify workflow: LLM analyzes → RAG finds solutions → LLM makes plan → tools execute
5. If fix fails → alarm logged to `/var/log/rdma_collector/alarms.json`

---

## Phase 9: Test the System

### 9.1 Test the Q&A Chatbot

1. In Dify, open `RDMA Knowledge Assistant`
2. Click **"Run"** (preview mode, top right)
3. Try these questions:
   - `How do I check if my RDMA port is active?`
   - `What causes RNR retry exceeded errors?`
   - `How do I configure PFC for RoCE?`
   - `What is the weather today?` (should answer directly, not using RAG)

### 9.2 Test the Auto-Monitor Workflow

1. In Dify, open `RDMA Auto-Monitor & Action Agent`
2. Click **"Run"** (preview mode)
3. Paste a test snapshot into `rdma_snapshot`:
```json
{
  "hostname": "rdma-server-01",
  "ibstat": "Port 1:\n  State: Down\n  Physical state: Polling",
  "dmesg_rdma": "mlx5_core: link down",
  "port_counters": "symbol_error: 150\nlink_downed: 3"
}
```
4. Set `health_status` to: `PORT_NOT_ACTIVE:mlx5_0/ports/1;ERROR_COUNTER:mlx5_0/ports/1/symbol_error=150`
5. Click **"Run"** and watch the workflow execute step by step

### 9.3 Test Agent Tools Directly

```bash
# Check status
curl -X POST http://localhost:5100/tools/rdma_check_status

# Check counters
curl -X POST http://localhost:5100/tools/rdma_check_counters \
  -H "Content-Type: application/json" \
  -d '{"device": "mlx5_0", "port": "1"}'

# Check PCIe
curl -X POST http://localhost:5100/tools/rdma_check_pcie
```

---

## Quick Reference: Ports

| Service | Port | Purpose |
|---------|------|---------|
| Dify Web UI | 80 | Main interface |
| Dify API | 80 (/v1) | Workflow/chatbot API (via nginx) |
| Agent Tools | 5100 | RDMA tool endpoints |
| Dify API (direct) | 5001 | Direct API access (bypass nginx) |
| PostgreSQL | 5432 | Dify metadata (internal) |
| Redis | 6379 | Dify cache (internal) |
| Weaviate | 8080 | Vector DB (internal) |

---

## Troubleshooting This Setup

**"Model not found" error in workflow:**
→ Go to Settings → Model Providers → verify your LLM shows green check

**Knowledge Retrieval returns nothing:**
→ Go to Knowledge → check indexing completed (no "processing" status)
→ Try lowering score threshold from 0.5 to 0.3

**Agent tools unreachable from Dify:**
→ Dify is in Docker, use `host.docker.internal` or machine IP, not `localhost`
→ Verify: `docker exec -it docker-api-1 curl http://host.docker.internal:5100/openapi.json`

**Monitor daemon gets 401 from Dify:**
→ Verify API key in monitor.conf matches the key from Dify → Access API page
