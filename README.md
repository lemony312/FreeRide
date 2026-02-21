# 🎢 FreeRide

### Your one-stop shop to play with ClawBot for FREE

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![OpenClaw Compatible](https://img.shields.io/badge/OpenClaw-Compatible-blue.svg)](https://github.com/openclaw/openclaw)
[![OpenRouter](https://img.shields.io/badge/OpenRouter-30%2B%20Free%20Models-orange.svg)](https://openrouter.ai)

---

**FreeRide** lets you run [OpenClaw](https://github.com/openclaw/openclaw) (ClawBot) completely free using OpenRouter's free AI models. No credit card. No trial period. Actually free.

```
You: *hits rate limit*
FreeRide: "I got you." *switches to next best model*
You: *keeps chatting*
```

## 🚀 Quick Start (5 Minutes)

### What You Need

| Account | Why | Link |
|---------|-----|------|
| **OpenRouter** (required) | Free AI models | [openrouter.ai/keys](https://openrouter.ai/keys) |
| **Brave Search** (optional) | Web search capability | [brave.com/search/api](https://brave.com/search/api/) |
| **Docker Desktop** (required) | Runs everything isolated | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop) |

### Step 1: Get Your Free OpenRouter Key

1. Go to [openrouter.ai/keys](https://openrouter.ai/keys)
2. Create an account (no credit card needed)
3. Click "Create Key"
4. Copy your key (starts with `sk-or-v1-...`)

### Step 2: Clone and Configure

```bash
# Clone this repo
git clone https://github.com/yourusername/freeride.git
cd freeride

# Create your config file
cp .env.example .env
```

Edit `.env` and paste your OpenRouter key:

```bash
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Optional: Enable web search (get key at brave.com/search/api)
BRAVE_API_KEY=your-brave-key-here
```

### Step 3: Run Setup

```bash
./setup.sh
```

This takes about 2-3 minutes the first time. It will:
- Build the Docker image
- Configure OpenClaw with free models
- Start the gateway
- Print your Control UI link

### Step 4: Start Chatting!

Open the **Control UI** link printed at the end:

```
http://localhost:18789/#token=your-token-here
```

That's it! You're now running ClawBot for free. 🎉

---

## 📱 What You Can Do

Once running, you can:

- **Chat** with your AI assistant in the Control UI
- **Search the web** (if you enabled Brave Search)
- **Run code** and use tools
- **Connect channels** like WhatsApp, Telegram, Discord

## ⚙️ Configuration Checklist

| Setting | Location | Required? |
|---------|----------|-----------|
| OpenRouter API Key | `.env` file | ✅ Yes |
| Brave Search API Key | `.env` file | ❌ Optional |
| Web Search Plugin | [openrouter.ai/settings/plugins](https://openrouter.ai/settings/plugins) | ❌ Optional (alternative to Brave) |

### Enable Web Search (Choose One)

**Option A: OpenRouter Plugin (Easiest)**
1. Go to [openrouter.ai/settings/plugins](https://openrouter.ai/settings/plugins)
2. Enable the **Web Search** plugin
3. Done - models can now search the web

**Option B: Brave Search API**
1. Get a key at [brave.com/search/api](https://brave.com/search/api/)
2. Add `BRAVE_API_KEY=your-key` to `.env`
3. Restart: `cd .docker-openclaw && docker compose restart`

---

## 🔧 Common Commands

### Docker Commands (run from `.docker-openclaw/` folder)

```bash
cd .docker-openclaw

# View logs
docker compose logs -f

# Restart
docker compose restart openclaw-gateway

# Stop everything
docker compose down

# Start again
docker compose up -d
```

### FreeRide Commands

```bash
# See all free models ranked by quality
python3 main.py list

# Auto-configure the best free model
python3 main.py auto

# Check current model status
python3 main.py status

# Use a specific model
python3 main.py switch qwen3-coder
```

**Important:** Always restart the gateway after changing models:
```bash
cd .docker-openclaw && docker compose restart openclaw-gateway
```

---

## 🆓 How It Works

FreeRide uses [OpenRouter](https://openrouter.ai), which provides free tiers for 30+ AI models including:

- **Qwen3** - Great for coding
- **Llama 3.3** - Strong general purpose
- **DeepSeek** - Excellent reasoning
- **Mistral** - Fast and reliable

When you hit a rate limit on one model, OpenClaw automatically switches to the next best free model. You keep working without interruption.

### What You Get

```
Primary Model: openrouter/openrouter/free (auto-selects best)

Fallbacks:
  1. qwen/qwen3-coder:free      ← Great for coding
  2. meta-llama/llama-3.3:free  ← Strong reasoning
  3. deepseek/deepseek:free     ← Fast responses
  4. mistral/mistral:free       ← Reliable fallback
```

---

## 🔍 Troubleshooting

| Problem | Solution |
|---------|----------|
| "gateway token missing" | Use the full URL with `#token=...` from setup output |
| "pairing required" | Run `docker exec -it docker-openclaw-openclaw-gateway-1 node dist/index.js configure` |
| "Control UI not loading" | Run `docker exec -u root -e CI=true docker-openclaw-openclaw-gateway-1 pnpm ui:build` |
| Rate limit errors | FreeRide auto-switches models, or run `python3 main.py auto` to refresh |
| Web search not working | Check your Brave API key or enable OpenRouter web search plugin |
| Container keeps restarting | Check logs: `docker logs docker-openclaw-openclaw-gateway-1` |

### Token Mismatch?

If the Control UI says "token mismatch", the gateway token changed. Get the current token:

```bash
grep "token" ~/.openclaw/openclaw.json
```

Use that token in your URL: `http://localhost:18789/#token=YOUR_TOKEN`

---

## 💰 The Math

| Scenario | Monthly Cost |
|----------|--------------|
| GPT-4 API | $50-200+ |
| Claude API | $50-200+ |
| OpenClaw + FreeRide | **$0** |

You're welcome.

---

## 📁 File Locations

| What | Where |
|------|-------|
| Main config | `~/.openclaw/openclaw.json` |
| Environment vars | `.env` and `.docker-openclaw/.env` |
| Docker files | `.docker-openclaw/` |
| FreeRide skill | `~/.openclaw/main.py` |

---

## ❓ FAQ

**Is this actually free?**

Yes. OpenRouter provides free tiers for many models. No credit card required.

**What about rate limits?**

That's the whole point of FreeRide. When you hit a rate limit, OpenClaw automatically tries the next model in your fallback list.

**Will it mess up my config?**

No. FreeRide only touches model settings. Your other OpenClaw config is preserved.

**Can I use web search?**

Yes! Either enable the OpenRouter web search plugin, or add a Brave Search API key to your `.env`.

**Do I need to restart after changes?**

Yes. Run `docker compose restart openclaw-gateway` after changing models or config.

---

## 🤝 Contributing

Found a bug? Want a feature? PRs welcome.

---

## 📚 Related

- [OpenClaw](https://github.com/openclaw/openclaw) - The AI coding agent
- [OpenRouter](https://openrouter.ai) - Free AI model router
- [Docker Desktop](https://www.docker.com/products/docker-desktop) - Container runtime

---

<p align="center">
  <b>Stop paying. Start riding free.</b>
  <br><br>
  <a href="https://github.com/yourusername/freeride">⭐ Star on GitHub</a>
  ·
  <a href="https://openrouter.ai/keys">🔑 Get Free OpenRouter Key</a>
  ·
  <a href="https://github.com/openclaw/openclaw">🦞 Learn about OpenClaw</a>
</p>
