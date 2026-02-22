# OpenClaw Setup Guide (M1 Mac + OpenRouter)

**Target:** Match V1 Docker agent LLM config
**Model:** `qwen/qwen3-coder-next` via OpenRouter

---

## Step 1: Install OpenClaw

```bash
cd agentic_lab
curl -fsSL https://openclaw.ai/install.sh | bash
```

**Expected output:** Version `2026.2.21-2` or later

---

## Step 2: Verify Installation

```bash
openclaw --version
openclaw help
```

---

## Step 3: Configure OpenRouter

### Option A: Quick CLI Setup (Recommended)

```bash
export OPENROUTER_API_KEY="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"

openclaw onboard --auth-choice apiKey \
  --token-provider openrouter \
  --token "$OPENROUTER_API_KEY"
```

### Option B: Manual Config File

Edit `~/.openclaw/openclaw.json`:

```json
{
  "env": {
    "OPENROUTER_API_KEY": "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"
  },
  "agents": {
    "defaults": {
      "model": {
        "provider": "openrouter",
        "model": "qwen/qwen3-coder-next"
      }
    }
  }
}
```

---

## Step 4: Install Daemon (Background Service)

```bash
openclaw onboard --install-daemon
```

This installs LaunchAgent for 24/7 operation.

---

## Step 5: Start Gateway

```bash
# Start manually
openclaw gateway run

# Or check if daemon is running
launchctl list | grep openclaw
```

---

## Step 6: Test Query

```bash
# Simple test
openclaw send --query "What is 2+2?"

# Test with web search
openclaw send --query "What is the capital of France?"

# Test coding task
openclaw send --query "Write a Python function to reverse a string"
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `command not found` | `export PATH="$(npm config get prefix)/bin:$PATH"` |
| Sharp build errors | `SHARP_IGNORE_GLOBAL_LIBVIPS=1 npm install -g openclaw@latest` |
| Daemon not running | `openclaw onboard --install-daemon` |
| Permission denied | `chmod +x $(npm root -g)/openclaw/dist/cli.js` |

---

## Configuration Files

| Location | Purpose |
|----------|---------|
| `~/.openclaw/openclaw.json` | Main config |
| `~/Library/LaunchAgents/openclaw.*.plist` | Daemon config |
| `~/.openclaw/workspace/` | Working directory |

---

## Next Steps

1. Complete installation
2. Test with simple query
3. Compare with V1 Docker agent on same task
4. Document results in `agentic_lab/`
