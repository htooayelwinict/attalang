# Add to ~/.openclaw/openclaw.json

Add this to your config file (or use dashboard):

```json
{
  "wizard": {
    "lastRunAt": "2026-02-22T10:03:27.365Z",
    "lastRunVersion": "2026.2.21-2",
    "lastRunCommand": "doctor",
    "lastRunMode": "local"
  },
  "agents": {
    "defaults": {
      "compaction": {
        "mode": "safeguard"
      },
      "maxConcurrent": 4,
      "subagents": {
        "maxConcurrent": 8
      },
      "model": {
        "provider": "openrouter",
        "model": "qwen/qwen3-coder-next",
        "apiKey": "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",
        "baseUrl": "https://openrouter.ai/api/v1"
      }
    }
  },
  "messages": {
    "ackReactionScope": "group-mentions"
  },
  "commands": {
    "native": "auto",
    "nativeSkills": "auto",
    "restart": true,
    "ownerDisplay": "raw"
  },
  "gateway": {
    "auth": {
      "mode": "token",
      "token": "e6acaf9bd05ce947cd12efb24d6b33a23e748ff4872e3303"
    }
  },
  "meta": {
    "lastTouchedVersion": "2026.2.21-2",
    "lastTouchedAt": "2026-02-22T10:03:27.382Z"
  },
  "env": {
    "OPENROUTER_API_KEY": "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"
  }
}
```

## Quick Edit Command
```bash
nano ~/.openclaw/openclaw.json
# Then restart: openclaw daemon restart
```

## Or Use Dashboard (Easier)
http://127.0.0.1:18789 → Settings → LLM Providers → Add OpenRouter
