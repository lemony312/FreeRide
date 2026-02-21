# FreeRide Docker Setup

Run OpenClaw with FreeRide in an isolated Docker container.

## Quick Start

```bash
# 1. Set your API key
cp .env.example .env
# Edit .env and add your key from https://openrouter.ai/keys

# 2. Run setup (builds Docker, configures everything)
./setup.sh
```

The setup script handles everything: cloning OpenClaw, building Docker images, 
configuring the gateway, and setting up FreeRide. Open the Control UI link it prints.

## Prerequisites

1. Docker Desktop installed and running
2. OpenRouter API key (free at https://openrouter.ai/keys)
3. (Optional) Brave Search API key for web search (https://brave.com/search/api/)

## Manual Setup

If you prefer to set things up manually:

### 1. Configure Environment

Create `.env` in the project root:
```bash
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Optional: Enable web search
BRAVE_API_KEY=your-brave-api-key-here
```

### 2. Run docker-setup.sh

```bash
./docker-setup.sh
```

This will:
- Clone OpenClaw to `.docker-openclaw/`
- Build the Docker image
- Generate a gateway token
- Start the containers

## Usage

### Access Control UI

Open http://localhost:18789 in your browser.

If you see "unauthorized: gateway token missing":
1. Go to Settings in the Control UI
2. Paste your `OPENCLAW_GATEWAY_TOKEN` value

### Run FreeRide Commands

```bash
# List free models
docker exec -e OPENROUTER_API_KEY="sk-or-v1-..." \
  docker-openclaw-openclaw-gateway-1 \
  python3 /home/clawuser/.openclaw/main.py list --profile coding

# Auto-configure best model
docker exec -e OPENROUTER_API_KEY="sk-or-v1-..." \
  docker-openclaw-openclaw-gateway-1 \
  python3 /home/clawuser/.openclaw/main.py auto --profile coding

# IMPORTANT: Restart after model changes
docker compose restart openclaw-gateway
```

### Interactive TUI

```bash
docker exec -it docker-openclaw-openclaw-gateway-1 node dist/index.js tui
```

## Important: Restart After Model Changes

**Every time FreeRide changes the model configuration, restart the gateway:**

```bash
docker compose restart openclaw-gateway
```

Without this, OpenClaw continues using the old model.

## Security

The Docker container only has access to:
- `~/.openclaw` - OpenClaw configuration
- `~/.openclaw/workspace` - Workspace files

It does NOT have access to your main filesystem.

## Common Commands

| Action | Command |
|--------|---------|
| Start | `docker compose up -d` |
| Stop | `docker compose down` |
| Restart gateway | `docker compose restart openclaw-gateway` |
| View logs | `docker logs docker-openclaw-openclaw-gateway-1 -f` |
| Check status | `docker ps \| grep openclaw` |
| Shell access | `docker exec -it docker-openclaw-openclaw-gateway-1 bash` |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "pairing required" | Run `docker exec -it <container> node dist/index.js configure` |
| "gateway token missing" | Paste token into Control UI Settings |
| "Control UI assets not found" | Run `docker exec -u root -e CI=true <container> pnpm ui:build` |
| Container keeps restarting | Check logs: `docker logs <container>` |
| Models not changing | Restart gateway after FreeRide commands |

## Web Search

OpenClaw supports web search through multiple providers:

### Option 1: OpenRouter Web Search (Recommended)

If you're using OpenRouter, enable web search in their plugins:

1. Go to https://openrouter.ai/settings/plugins
2. Enable the **Web Search** plugin
3. This allows models to search the web directly through OpenRouter

This is the easiest option if you're already using OpenRouter for your models.

### Option 2: Brave Search API

For dedicated web search with more control:

1. Get an API key at https://brave.com/search/api/
2. Add to your `.env`:
   ```bash
   BRAVE_API_KEY=your-key-here
   ```
3. Restart the container:
   ```bash
   docker compose down && docker compose up -d
   ```

**Note:** Brave's free tier has limited monthly queries. For heavy usage, consider adding credits to your account.

### Option 3: Perplexity via OpenRouter

Use Perplexity Sonar for AI-synthesized search results:

1. Add to `~/.openclaw/openclaw.json`:
   ```json
   {
     "tools": {
       "web": {
         "search": {
           "provider": "perplexity"
         }
       }
     }
   }
   ```
2. Requires OpenRouter credits (not free tier)

## File Locations

| Host | Container |
|------|-----------|
| `~/.openclaw/openclaw.json` | `/home/clawuser/.openclaw/openclaw.json` |
| `~/.openclaw/main.py` | `/home/clawuser/.openclaw/main.py` |
| `.docker-openclaw/.env` | Environment variables |
