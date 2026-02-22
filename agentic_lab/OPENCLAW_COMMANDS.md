# OpenClaw Quick Reference

## Your OpenRouter Config
```
API Key: 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
Model: qwen/qwen3-coder-next
Base URL: https://openrouter.ai/api/v1
```

## Essential Commands

```bash
# Installation & Setup
curl -fsSL https://openclaw.ai/install.sh | bash
openclaw onboard --install-daemon

# Configuration (Manual)
nano ~/.openclaw/openclaw.json

# Start/Stop
openclaw gateway run          # Start foreground
openclaw gateway stop          # Stop
launchctl list | grep openclaw # Check daemon

# Queries
openclaw send --query "your question here"

# Skills/Tools
openclaw skills list           # List available skills
openclaw logs                  # View logs

# Status
openclaw status                # Check status
openclaw doctor                # Diagnose issues
```

## Manual Config Template

`~/.openclaw/openclaw.json`:
```json
{
  "env": {
    "OPENROUTER_API_KEY": "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"
  },
  "agents": {
    "defaults": {
      "model": {
        "provider": "openrouter",
        "model": "qwen/qwen3-coder-next",
        "apiKey": "$OPENROUTER_API_KEY"
      }
    }
  },
  "gateway": {
    "enabled": true
  }
}
```

## Test Queries (Same as V1 Docker Agent)

```bash
# Simple task
openclaw send --query "List all Docker containers"

# Complex task
openclaw send --query "Create a nginx container and expose port 80"

# Multi-step
openclaw send --query "Deploy postgres, redis, and nginx with networking"
```

## Logs Location
```
~/.openclaw/logs/
```
