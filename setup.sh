#!/bin/bash
# FreeRide Setup Script
# Run this to set up FreeRide with OpenClaw in Docker

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚗 FreeRide Setup"
echo "=================="
echo ""

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker Desktop first."
    echo "   https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

echo "✓ Docker is running"

# Create .env from example if it doesn't exist
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✓ Created .env from .env.example"
    fi
fi

# Check for API key
if [ -z "$OPENROUTER_API_KEY" ]; then
    if [ -f ".env" ]; then
        source .env
    fi
fi

if [ -z "$OPENROUTER_API_KEY" ] || [ "$OPENROUTER_API_KEY" = "sk-or-v1-your-key-here" ]; then
    echo ""
    echo "⚠️  OpenRouter API key not set!"
    echo ""
    echo "1. Get your free API key at: https://openrouter.ai/keys"
    echo "2. Edit .env and set: OPENROUTER_API_KEY=sk-or-v1-your-key"
    echo "3. Run this script again"
    echo ""
    exit 1
fi

echo "✓ OpenRouter API key found"

# Create OpenClaw directories
mkdir -p ~/.openclaw/workspace
mkdir -p ~/.openclaw/credentials
chmod 700 ~/.openclaw
echo "✓ Created ~/.openclaw directories"

# Copy FreeRide skill files
cp main.py profiles.py benchmarks.json skill.json SKILL.md ~/.openclaw/
echo "✓ Installed FreeRide skill to ~/.openclaw"

# Set up Docker environment
cd .docker-openclaw

# Use existing token from openclaw.json if available, otherwise generate new one
if [ -f ~/.openclaw/openclaw.json ]; then
    EXISTING_TOKEN=$(grep -o '"token": "[^"]*"' ~/.openclaw/openclaw.json 2>/dev/null | cut -d'"' -f4)
    if [ -n "$EXISTING_TOKEN" ]; then
        OPENCLAW_GATEWAY_TOKEN="$EXISTING_TOKEN"
        echo "✓ Using existing gateway token"
    fi
fi

if [ -z "$OPENCLAW_GATEWAY_TOKEN" ]; then
    OPENCLAW_GATEWAY_TOKEN=$(openssl rand -hex 32)
    echo "✓ Generated new gateway token"
fi

# Load Brave API key if set
if [ -f "$SCRIPT_DIR/.env" ]; then
    source "$SCRIPT_DIR/.env"
fi

# Create/update Docker .env
cat > .env << EOF
# OpenClaw Docker Configuration (auto-generated)
OPENCLAW_GATEWAY_TOKEN=${OPENCLAW_GATEWAY_TOKEN}
OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
BRAVE_API_KEY=${BRAVE_API_KEY:-}
OPENCLAW_CONFIG_DIR=${HOME}/.openclaw
OPENCLAW_WORKSPACE_DIR=${HOME}/.openclaw/workspace
OPENCLAW_GATEWAY_PORT=18789
OPENCLAW_BRIDGE_PORT=18790
OPENCLAW_GATEWAY_BIND=lan
OPENCLAW_IMAGE=openclaw:local
EOF
echo "✓ Created Docker .env"

# Create minimal OpenClaw config if it doesn't exist
if [ ! -f ~/.openclaw/openclaw.json ]; then
    cat > ~/.openclaw/openclaw.json << JSONEOF
{
  "gateway": {
    "mode": "local",
    "auth": {
      "token": "${OPENCLAW_GATEWAY_TOKEN}"
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "openrouter/openrouter/free"
      }
    }
  },
  "env": {
    "OPENROUTER_API_KEY": "${OPENROUTER_API_KEY}"
  }
}
JSONEOF
    echo "✓ Created OpenClaw config"
else
    echo "✓ OpenClaw config exists"
fi

# Build Docker image
echo ""
echo "Building OpenClaw Docker image (this may take a few minutes)..."
docker compose build 2>&1 | tail -10

# Start containers (skip interactive onboard - config already exists)
echo ""
echo "Starting OpenClaw..."
docker compose up -d openclaw-gateway 2>&1

# Wait for container to start
echo "Waiting for gateway to start..."
sleep 5

# Check if running
if docker ps | grep -q "openclaw-gateway"; then
    echo "✓ OpenClaw gateway is running!"
else
    echo "⚠️  Gateway may still be starting. Check with: docker compose logs -f"
fi

# Build Control UI
echo ""
echo "Building Control UI..."
docker exec -u root -e CI=true docker-openclaw-openclaw-gateway-1 pnpm ui:build 2>&1 | tail -5 || echo "UI build will complete on first access"

# Restart to ensure everything is loaded
docker compose restart openclaw-gateway 2>&1
sleep 3

# Configure FreeRide
echo ""
echo "Configuring FreeRide with best free model..."
cd "$SCRIPT_DIR"
source .env
python3 main.py auto --profile coding 2>&1 || echo "FreeRide config will be done on first use"

# Final restart to apply model config
cd .docker-openclaw
docker compose restart openclaw-gateway 2>&1
sleep 2

echo ""
echo "=============================================="
echo "🎉 FreeRide Setup Complete!"
echo "=============================================="
echo ""
echo "Control UI: http://localhost:18789/#token=${OPENCLAW_GATEWAY_TOKEN}"
echo ""
echo "Commands:"
echo "  cd .docker-openclaw && docker compose logs -f    # View logs"
echo "  cd .docker-openclaw && docker compose restart    # Restart"
echo "  cd .docker-openclaw && docker compose down       # Stop"
echo ""
echo "FreeRide Commands:"
echo "  python3 main.py list      # List free models"
echo "  python3 main.py auto      # Auto-select best model"
echo "  python3 main.py status    # Check status"
echo ""
