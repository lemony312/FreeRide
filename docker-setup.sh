#!/bin/bash
# FreeRide + OpenClaw - Complete Docker Setup
# 
# This script sets up OpenClaw in Docker with FreeRide pre-installed.
# Everything runs in containers - nothing installed on your host.
#
# Usage:
#   ./docker-setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$SCRIPT_DIR/.docker-openclaw"

echo "=========================================="
echo "FreeRide + OpenClaw Docker Setup"
echo "=========================================="
echo ""
echo "This will:"
echo "  1. Clone OpenClaw into .docker-openclaw/"
echo "  2. Build OpenClaw Docker image"
echo "  3. Install FreeRide skill"
echo "  4. Configure with your API key"
echo ""
echo "Everything runs in Docker - nothing on your host."
echo ""

# Check for API key
if [ -f "$SCRIPT_DIR/.env" ]; then
    source "$SCRIPT_DIR/.env"
fi

if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "ERROR: OPENROUTER_API_KEY not set"
    echo ""
    echo "Create .env file first:"
    echo "  echo 'OPENROUTER_API_KEY=sk-or-v1-xxxx' > .env"
    exit 1
fi

echo "API key found: ${OPENROUTER_API_KEY:0:12}...${OPENROUTER_API_KEY: -4}"
echo ""

# Clone OpenClaw if not exists
if [ ! -d "$WORK_DIR" ]; then
    echo "Cloning OpenClaw..."
    git clone --depth 1 https://github.com/openclaw/openclaw.git "$WORK_DIR"
else
    echo "OpenClaw already cloned at $WORK_DIR"
fi

cd "$WORK_DIR"

# Copy FreeRide skill into OpenClaw's workspace location
echo ""
echo "Copying FreeRide skill..."
mkdir -p skills/free-ride
cp -r "$SCRIPT_DIR"/*.py "$SCRIPT_DIR"/*.json "$SCRIPT_DIR"/*.md "$SCRIPT_DIR"/setup.py skills/free-ride/ 2>/dev/null || true

# Create a custom Dockerfile that includes FreeRide
echo ""
echo "Creating custom Dockerfile with FreeRide..."
cat > Dockerfile.freeride << 'DOCKERFILE'
# OpenClaw + FreeRide
FROM node:22-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Create app directory
WORKDIR /app

# Copy OpenClaw source
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile || pnpm install

COPY . .
RUN pnpm build || echo "Build step optional"

# Create openclaw user
RUN useradd -m -s /bin/bash clawuser \
    && mkdir -p /home/clawuser/.openclaw/workspace/skills \
    && chown -R clawuser:clawuser /home/clawuser

# Copy and install FreeRide
COPY skills/free-ride /home/clawuser/.openclaw/workspace/skills/free-ride
RUN chown -R clawuser:clawuser /home/clawuser/.openclaw

USER clawuser
WORKDIR /home/clawuser

# Install FreeRide in user space
RUN python3 -m venv /home/clawuser/.openclaw/workspace/skills/free-ride/.venv \
    && /home/clawuser/.openclaw/workspace/skills/free-ride/.venv/bin/pip install -e /home/clawuser/.openclaw/workspace/skills/free-ride

ENV PATH="/home/clawuser/.openclaw/workspace/skills/free-ride/.venv/bin:/app/node_modules/.bin:$PATH"
ENV HOME="/home/clawuser"

EXPOSE 18789

CMD ["node", "/app/dist/index.js", "gateway", "start", "--bind", "0.0.0.0"]
DOCKERFILE

# Create docker-compose for easy management
cat > docker-compose.freeride.yml << COMPOSE
services:
  openclaw:
    build:
      context: .
      dockerfile: Dockerfile.freeride
    container_name: openclaw-freeride
    ports:
      - "127.0.0.1:18789:18789"
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
    volumes:
      - openclaw-data:/home/clawuser/.openclaw
    restart: unless-stopped

volumes:
  openclaw-data:
COMPOSE

echo ""
echo "Building Docker image (this may take a few minutes)..."
docker compose -f docker-compose.freeride.yml build

echo ""
echo "Starting OpenClaw..."
docker compose -f docker-compose.freeride.yml up -d

echo ""
echo "Waiting for startup..."
sleep 5

echo ""
echo "Configuring FreeRide..."
docker compose -f docker-compose.freeride.yml exec -T openclaw bash -c "
    cd /home/clawuser/.openclaw/workspace/skills/free-ride
    .venv/bin/freeride auto --profile coding
" || echo "FreeRide config will be done on first use"

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "OpenClaw is running at: http://127.0.0.1:18789"
echo ""
echo "Commands:"
echo "  cd $WORK_DIR"
echo "  docker compose -f docker-compose.freeride.yml logs -f    # View logs"
echo "  docker compose -f docker-compose.freeride.yml exec openclaw bash  # Shell"
echo "  docker compose -f docker-compose.freeride.yml down       # Stop"
echo ""
echo "To use FreeRide inside the container:"
echo "  docker compose -f docker-compose.freeride.yml exec openclaw freeride list --profile coding"
echo ""
