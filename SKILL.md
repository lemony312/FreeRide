---
name: freeride
description: Manages free AI models from OpenRouter for OpenClaw. Ranks models by quality using benchmark tiers and use-case profiles (coding, reasoning, general, vision). Use when the user mentions free AI, OpenRouter, model switching, rate limits, coding models, or wants to reduce AI costs.
---

# FreeRide - Free AI for OpenClaw

## What This Skill Does

Configures OpenClaw to use **free** AI models from OpenRouter. Ranks models using benchmark-based quality tiers and supports **use-case profiles** for optimal model selection. Sets the best free model as primary, adds ranked fallbacks so rate limits don't interrupt the user, and preserves existing config.

## Use-Case Profiles

FreeRide supports four profiles that optimize model selection for different tasks:

| Profile | Best For | Prioritizes |
|---------|----------|-------------|
| `coding` | Code generation, completion, debugging | Coding-specific models, tool support, large context |
| `reasoning` | Complex analysis, problem-solving | Thinking/reasoning models (DeepSeek-R1, Qwen-thinking) |
| `general` | Chat, general assistance | Balanced quality, well-rounded models |
| `vision` | Image understanding, multimodal | Vision-capable models only |

## Prerequisites

Before running any FreeRide command, ensure:

1. **OPENROUTER_API_KEY is set.** Check with `echo $OPENROUTER_API_KEY`. If empty, the user must get a free key at https://openrouter.ai/keys and set it:
   ```bash
   export OPENROUTER_API_KEY="sk-or-v1-..."
   # Or persist it:
   openclaw config set env.OPENROUTER_API_KEY "sk-or-v1-..."
   ```

2. **The `freeride` CLI is installed.** Check with `which freeride`. If not found:
   ```bash
   cd ~/.openclaw/workspace/skills/free-ride
   pip install -e .
   ```

## Primary Workflow

When the user wants free AI, run these steps in order:

```bash
# Step 1: Configure best free model + fallbacks (use profile for their use case)
freeride auto --profile coding    # For developers
freeride auto --profile reasoning # For analysis tasks
freeride auto --profile general   # For general chat (default)
freeride auto --profile vision    # For image tasks

# Step 2: Restart gateway so OpenClaw picks up the changes
openclaw gateway restart
```

That's it. The user now has free AI with automatic fallback switching.

Verify by telling the user to send `/status` to check the active model.

## Commands Reference

### Core Commands

| Command | When to use it |
|---------|----------------|
| `freeride auto` | User wants free AI set up (most common) |
| `freeride auto --profile coding` | User is a developer, wants best coding model |
| `freeride auto --profile reasoning` | User needs complex analysis/problem-solving |
| `freeride auto -f` | User wants fallbacks but wants to keep their current primary model |
| `freeride auto -c 10` | User wants more fallbacks (default is 5) |
| `freeride list` | User wants to see available free models |
| `freeride list --profile coding` | User wants to see models ranked for coding |
| `freeride list -n 30` | User wants to see all free models |
| `freeride switch <model>` | User wants a specific model (e.g. `freeride switch qwen3-coder`) |
| `freeride switch <model> -f` | Add specific model as fallback only |

### Utility Commands

| Command | When to use it |
|---------|----------------|
| `freeride status` | Check current FreeRide configuration |
| `freeride fallbacks` | Update only the fallback models |
| `freeride fallbacks --profile coding` | Update fallbacks ranked for coding |
| `freeride refresh` | Force refresh the cached model list |
| `freeride benchmarks` | View quality tiers and benchmark data |

### Profile Options

All ranking commands (`list`, `auto`, `switch`, `fallbacks`) accept `--profile` or `-p`:

```bash
freeride list -p coding      # Rank models for coding
freeride auto -p reasoning   # Select best reasoning model
freeride fallbacks -p vision # Configure vision-capable fallbacks
```

**After any command that changes config, always run `openclaw gateway restart`.**

## Model Quality Tiers

FreeRide uses benchmark-based quality tiers to rank models:

| Tier | Score | Examples |
|------|-------|----------|
| S | 1.0 | DeepSeek-R1, Qwen3-235B, Llama-3.3-70B, Qwen3-Coder |
| A | 0.8 | Qwen3 variants, Nvidia Nemotron, Mistral-Small |
| B | 0.6 | Llama variants, Google Gemma, Arcee Trinity |
| C | 0.4 | Smaller/newer models with limited benchmarks |

View current tiers with `freeride benchmarks`.

## What It Writes to Config

FreeRide updates only these keys in `~/.openclaw/openclaw.json`:

- `agents.defaults.model.primary` — e.g. `openrouter/qwen/qwen3-coder:free`
- `agents.defaults.model.fallbacks` — e.g. `["openrouter/free", "nvidia/nemotron:free", ...]`
- `agents.defaults.models` — allowlist so `/model` command shows the free models

Everything else (gateway, channels, plugins, env, customInstructions, named agents) is preserved.

The first fallback is always `openrouter/free` — OpenRouter's smart router that auto-picks the best available model based on the request.

## Watcher (Optional)

For auto-rotation when rate limited, the user can run:

```bash
freeride-watcher --daemon    # Continuous monitoring
freeride-watcher --rotate    # Force rotate now
freeride-watcher --status    # Check rotation history
```

## Debugging / Development

### IMPORTANT: Restart After Model Changes

**Every time FreeRide changes the model configuration, you MUST restart the gateway:**

```bash
# After any model change (auto, switch, fallbacks)
freeride auto --profile coding
openclaw gateway restart   # <-- REQUIRED

# In Docker
docker compose restart openclaw-gateway
```

Without restarting, OpenClaw will continue using the old model configuration.

### Control UI Token

If the Control UI shows "unauthorized: gateway token missing":

1. Open http://localhost:18789 in your browser
2. Go to Settings
3. Paste your gateway token (found in `.env` as `OPENCLAW_GATEWAY_TOKEN`)

### Docker Quick Reference

```bash
# Start OpenClaw
cd ~/.openclaw-docker && docker compose up -d

# Check status
docker ps | grep openclaw

# View logs
docker logs docker-openclaw-openclaw-gateway-1 -f

# Restart after model changes
docker compose restart openclaw-gateway

# Run FreeRide commands
docker exec -e OPENROUTER_API_KEY="your-key" docker-openclaw-openclaw-gateway-1 \
  python3 /home/clawuser/.openclaw/main.py auto --profile coding

# Open TUI (interactive terminal)
docker exec -it docker-openclaw-openclaw-gateway-1 node dist/index.js tui

# Build Control UI (if missing)
docker exec -u root -e CI=true docker-openclaw-openclaw-gateway-1 pnpm ui:build
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `freeride: command not found` | `cd ~/.openclaw/workspace/skills/free-ride && pip install -e .` |
| `OPENROUTER_API_KEY not set` | User needs a key from https://openrouter.ai/keys |
| Changes not taking effect | **`openclaw gateway restart`** then `/new` for fresh session |
| Agent shows 0 tokens | Check `freeride status` — primary should be `openrouter/<provider>/<model>:free` |
| Control UI "unauthorized" | Paste gateway token into Control UI Settings |
| Control UI "assets not found" | Run `pnpm ui:build` (or in Docker: `docker exec -u root -e CI=true <container> pnpm ui:build`) |
| Docker "pairing required" | Run `docker exec -it <container> node dist/index.js configure` and set gateway mode to "local" |