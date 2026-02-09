# Dify Model Provider Setup Guide

## Step 1: Add Local LLM as OpenAI-compatible Provider

1. Go to Dify → Settings → Model Providers
2. Click "OpenAI-API-compatible"
3. Configure:
   - **Model Name**: your-model-name
   - **API Base URL**: `http://your-llm-host:8000/v1`
   - **API Key**: your-llm-api-key
   - **Model Type**: LLM
   - **Context Size**: Set according to your model
   - **Max Tokens**: Set according to your model
4. Save and test the connection

## Step 2: Add Embedding Model

1. Go to Dify → Settings → Model Providers
2. Click "OpenAI-API-compatible"
3. Configure:
   - **Model Name**: your-embedding-model
   - **API Base URL**: `http://your-embedding-host:8001/v1`
   - **API Key**: your-embedding-api-key
   - **Model Type**: Text Embedding
4. Save and test

## Step 3: Add Rerank Model

1. Go to Dify → Settings → Model Providers
2. Click "OpenAI-API-compatible"
3. Configure:
   - **Model Name**: your-rerank-model
   - **API Base URL**: `http://your-rerank-host:8002/v1`
   - **API Key**: your-rerank-api-key
   - **Model Type**: Rerank
4. Save and test

## Step 4: Configure Qdrant as Vector Store

In your Dify `.env` file (the Dify deployment env, not this project):

```env
VECTOR_STORE=qdrant
QDRANT_URL=http://your-qdrant-host:6333
QDRANT_API_KEY=your-qdrant-api-key
```

Restart Dify after changing the vector store setting.

## Step 5: Create Knowledge Base

1. Go to Dify → Knowledge
2. Click "Create Knowledge"
3. Name it "RDMA Knowledge Base"
4. Upload files from `knowledge_base/` directory:
   - `rdma_docs/rdma_fundamentals.md`
   - `troubleshooting/rdma_common_issues.md`
   - `troubleshooting/rdma_action_plans.md`
5. Configure indexing:
   - **Indexing Mode**: High Quality
   - **Embedding Model**: Select your embedding model
   - **Chunk Size**: 800-1000 tokens recommended
   - **Chunk Overlap**: 100-150 tokens
6. Enable reranking in retrieval settings
7. Note the Knowledge Base ID for workflow configuration
