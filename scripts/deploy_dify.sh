#!/usr/bin/env bash
# Dify POC Deployment Script
# Run this on your target server to deploy Dify with all defaults.
# Requires: Docker, Docker Compose, Git

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DIFY_DIR="${PROJECT_DIR}/dify-docker"

echo "========================================="
echo "  Dify POC Deployment"
echo "========================================="

# Step 1: Clone Dify if not already present
if [ ! -d "$DIFY_DIR" ]; then
    echo "[1/4] Cloning Dify repository..."
    git clone --depth 1 https://github.com/langgenius/dify.git "$DIFY_DIR"
else
    echo "[1/4] Dify directory already exists, skipping clone."
fi

# Step 2: Set up environment
echo "[2/4] Setting up environment..."
cd "${DIFY_DIR}/docker"

if [ ! -f .env ]; then
    cp .env.example .env

    # Set admin password for easy access
    sed -i 's/^INIT_PASSWORD=$/INIT_PASSWORD=dify123456/' .env

    echo "  .env created from template"
    echo "  Admin password set to: dify123456"
else
    echo "  .env already exists, skipping."
fi

# Step 3: Start services
echo "[3/4] Starting Dify services..."
docker compose up -d

# Step 4: Wait and verify
echo "[4/4] Waiting for services to start..."
sleep 30

echo ""
echo "========================================="
echo "  Checking service status..."
echo "========================================="
docker compose ps

echo ""
echo "========================================="
echo "  Deployment Complete!"
echo "========================================="
echo ""
echo "  Dify URL:       http://localhost/install"
echo "  Admin Password: dify123456"
echo ""
echo "  Services included (all local, no external DB needed):"
echo "    - PostgreSQL (metadata store)"
echo "    - Redis (cache & message broker)"
echo "    - Weaviate (default vector store)"
echo "    - Nginx (reverse proxy)"
echo "    - Sandbox (code execution)"
echo "    - SSRF Proxy (security)"
echo ""
echo "  All data stored locally in:"
echo "    ${DIFY_DIR}/docker/volumes/"
echo ""
echo "  Next steps:"
echo "    1. Open http://localhost/install in your browser"
echo "    2. Create admin account (password: dify123456)"
echo "    3. Follow config/dify_model_provider_setup.md to add your models"
echo "    4. Upload knowledge_base/ documents to create a Knowledge Base"
echo "    5. Build workflows using dify_workflows/ blueprints"
echo ""
echo "  To stop:  cd ${DIFY_DIR}/docker && docker compose down"
echo "  To start: cd ${DIFY_DIR}/docker && docker compose up -d"
echo "  Logs:     cd ${DIFY_DIR}/docker && docker compose logs -f"
