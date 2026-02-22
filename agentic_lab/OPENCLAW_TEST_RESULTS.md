# OpenClaw Test Results

**Date:** 2025-02-22
**OpenClaw Version:** 2026.2.21-2 (35a57bc)
**Model:** `qwen/qwen3-coder-next` (OpenRouter)

---

## Installation Status

- [x] OpenClaw installed
- [x] OpenRouter API configured
- [x] Gateway running on port 18789
- [x] Dashboard: http://127.0.0.1:18789

---

## Config Used

`~/.openclaw/openclaw.json`:
```json
{
  "models": {
    "mode": "merge",
    "providers": {
      "openrouter": {
        "baseUrl": "https://openrouter.ai/api/v1",
        "apiKey": "sk-or-v1-...",
        "api": "openai-completions",
        "models": [
          {
            "id": "qwen/qwen3-coder-next",
            "name": "Qwen3 Coder Next"
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "openrouter/qwen/qwen3-coder-next"
      }
    }
  },
  "gateway": {
    "mode": "local",
    "auth": {
      "mode": "token",
      "token": "e6acaf9bd05ce947cd12efb24d6b33a23e748ff4872e3303"
    }
  },
  "env": {
    "OPENROUTER_API_KEY": "sk-or-v1-..."
  }
}
```

---

## Test Results

### Test 1: Simple Query
**Prompt:** `What is 2+2?`

**OpenClaw Response:**
```
2 + 2 = 4
```

**V1 Docker Agent Response:** (N/A - not tested)

**Status:** ✅ Pass

---

### Test 2: Docker List
**Prompt:** `List all Docker containers`

**OpenClaw Response:**
```
No Docker containers found (running or stopped).
```

**Status:** ✅ Pass (Verified with `docker ps -a`)

---

### Test 3: Create Container
**Prompt:** `Create and run an nginx container named web-server with port 8080 mapped to 80`

**OpenClaw Response:**
```
Done! Nginx container `web-server` is now running with port 8080 mapped to 80.
```

**Verification:**
```
CONTAINER ID   IMAGE     COMMAND                  CREATED         STATUS         PORTS                                     NAMES
6e4b15946997   nginx     "/docker-entrypoint.…"   7 seconds ago   Up 6 seconds   0.0.0.0:8080->80/tcp, [::]:8080->80/tcp   web-server
```

**Status:** ✅ Pass

---

### Test 4: Multi-Step Deployment
**Prompt:** `Deploy a full stack: create network app-net, postgres container with env POSTGRES_PASSWORD=secret, redis container, and nginx container - all connected to app-net`

**OpenClaw Response:**
```
Full stack deployed successfully:

- **Network:** `app-net` created
- **Postgres:** running on `app-net` (port 5432, password: `secret`)
- **Redis:** running on `app-net` (port 6379)
- **Nginx:** running as `nginx-web` on `app-net`, mapped to host port `8081`

All containers are connected to the same network and can communicate with each other using their container names as hostnames.
```

**Verification:**
```
CONTAINER ID   IMAGE      COMMAND                  CREATED              STATUS              PORTS                                     NAMES
d2ceea18fc5a   nginx      "/docker-entrypoint.…"   22 seconds ago       Up 21 seconds       0.0.0.0:8081->80/tcp, [::]:8081->80/tcp   nginx-web
f3a6daec5e9c   redis      "docker-entrypoint.s…"   23 seconds ago       Up 23 seconds       6379/tcp                                  redis
d54f6facecae   postgres   "docker-entrypoint.s…"   32 seconds ago       Up 31 seconds       5432/tcp                                  postgres

NETWORK ID     NAME           DRIVER    SCOPE
5a65a342b815   app-net        bridge    local

Containers on app-net: nginx-web, postgres, redis
```

**Status:** ✅ Pass

---

## Commands Used

```bash
# Install
curl -fsSL https://openclaw.ai/install.sh | bash

# Configure (manual config edit)
nano ~/.openclaw/openclaw.json

# Start gateway
openclaw gateway run > agentic_lab/gateway.log 2>&1 &

# Run queries
openclaw agent --agent main --message "your prompt here"
```

---

## Observations

### OpenClaw Advantages:
- ✅ Quick installation (one-line)
- ✅ Clean, concise responses
- ✅ Successfully executed multi-step Docker deployment
- ✅ No verbose tool output (cleaner than V1)
- ✅ Works with same OpenRouter model
- ✅ Dashboard UI available

### OpenClaw Limitations:
- ⚠️ Requires manual config file editing (no direct OpenRouter option in wizard)
- ⚠️ CLI command structure different from expected (`agent --message` vs `send --query`)
- ⚠️ Need to specify agent (`--agent main`) for every query
- ⚠️ No built-in HITL (Human-in-the-Loop) for dangerous operations
- ⚠️ Token authentication warnings in logs

### V1 Docker Agent Advantages:
- ✅ Explicit HITL for dangerous tools
- ✅ Structured tool result handling
- ✅ Type-safe Pydantic state management
- ✅ More transparent tool execution (verbose mode)

### V1 Docker Agent Limitations:
- ⚠️ More verbose output
- ⚠️ Requires Python virtual environment

---

## Performance Notes

| Test | OpenClaw | Notes |
|------|----------|-------|
| Simple query | Fast | Instant response |
| Docker list | Fast | Direct execution |
| Create container | Medium | Planning + execution |
| Multi-step deploy | Slow (~10s) | Complex orchestration |

---

## Conclusion

**OpenClaw successfully handles the same Docker tasks as V1 Docker Agent** using the same OpenRouter model (`qwen/qwen3-coder-next`).

**Key Differences:**
1. OpenClaw has cleaner, more conversational responses
2. V1 has better transparency (verbose tool output)
3. V1 has HITL safety features
4. OpenClaw is quicker to set up (one-line install)

**Recommendation:** Use OpenClaw for quick tasks and V1 Docker Agent for complex/production workflows requiring safety controls.
