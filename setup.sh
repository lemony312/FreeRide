#!/bin/bash
# FreeRide Setup Script
# Run this to set up FreeRide with OpenClaw in Docker

set -e

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

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        # Generate a random gateway token
        GATEWAY_TOKEN=$(openssl rand -hex 32)
        
        # Create .env from example with actual values
        cat > .env << EOF
# OpenClaw Docker Configuration (auto-generated)
OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
OPENCLAW_GATEWAY_TOKEN=${GATEWAY_TOKEN}
OPENCLAW_CONFIG_DIR=${HOME}/.openclaw
OPENCLAW_WORKSPACE_DIR=${HOME}/.openclaw/workspace
OPENCLAW_GATEWAY_PORT=18789
OPENCLAW_BRIDGE_PORT=18790
OPENCLAW_GATEWAY_BIND=lan
OPENCLAW_IMAGE=docker-openclaw-openclaw:latest
EOF
        echo "✓ Created Docker .env with gateway token"
    fi
fi

# Build and start OpenClaw
echo ""
echo "Building OpenClaw Docker image (this may take a few minutes)..."
./docker-setup.sh 2>&1 | tail -20

if [ $? -ne 0 ]; then
    echo ""
    echo "⚠️  Build may have completed. Checking status..."
fi

# Wait for container to start
sleep 5

# Check if running
if docker ps | grep -q "openclaw-gateway"; then
    echo ""
    echo "✓ OpenClaw is running!"
else
    echo ""
    echo "Starting OpenClaw..."
    docker compose up -d 2>&1
    sleep 5
fi

# Configure FreeRide
echo ""
echo "Configuring FreeRide..."
cd ..
source .env
python3 main.py auto --profile coding 2>&1 || true

# Restart gateway to apply config
cd .docker-openclaw
docker compose restart openclaw-gateway 2>&1
sleep 3

# Build Control UI
echo ""
echo "Building Control UI..."
docker exec -u root -e CI=true docker-openclaw-openclaw-gateway-1 pnpm ui:build 2>&1 | tail -5 || true

# Final restart
docker compose restart openclaw-gateway 2>&1
sleep 3

# Get dashboard URL
GATEWAY_TOKEN=$(grep "^OPENCLAW_GATEWAY_TOKEN=" .env | cut -d= -f2)

echo ""
echo "=============================================="
echo "🎉 FreeRide Setup Complete!"
echo "=============================================="
echo ""
echo "Control UI: http://localhost:18789/#token=${GATEWAY_TOKEN}"
echo ""
echo "Commands:"
echo "  docker compose logs -f    # View logs"
echo "  docker compose restart    # Restart"
echo "  docker compose down       # Stop"
echo ""
echo "FreeRide Commands:"
echo "  python3 main.py list      # List free models"
echo "  python3 main.py auto      # Auto-select best model"
echo "  python3 main.py status    # Check status"
echo ""
