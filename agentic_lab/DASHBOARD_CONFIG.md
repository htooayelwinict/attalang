# OpenClaw Dashboard Config (OpenRouter)

**Dashboard:** http://127.0.0.1:18789
**Token:** `e6acaf9bd05ce947cd12efb24d6b33a23e748ff4872e3303`

---

## Step 1: Add OpenRouter in Dashboard

1. Open dashboard URL
2. Go to **Settings** → **LLM Providers**
3. Add **OpenRouter**:
   - **API Key:** `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`
   - **Model:** `qwen/qwen3-coder-next`
   - **Base URL:** `https://openrouter.ai/api/v1`

---

## Step 2: Set Default Model

In **Settings** → **Agent** → **Default Model**:
- Provider: `openrouter`
- Model: `qwen/qwen3-coder-next`

---

## Step 3: Enable Tools (if needed)

**Settings** → **Skills/Tools** → Enable:
- Web Search
- File System (careful!)
- Terminal/Shell (careful!)
- Docker (if available)

---

## Step 4: Test via Dashboard

Use the chat in dashboard:
```
What is 2+2?
```

---

## Step 5: Test via CLI

```bash
# Test query
openclaw send --query "What is the capital of France?"

# Test Docker task (same as V1)
openclaw send --query "List all Docker containers"

# Test coding
openclaw send --query "Write a Python function to calculate fibonacci numbers"
```

---

## Step 6: Compare with V1 Docker Agent

Run same prompts in both:
```bash
# V1 Docker Agent
.venv/bin/python -m src.multi_agent.runtime.cli --prompt "list all containers"

# OpenClaw
openclaw send --query "List all Docker containers"
```

Document results in `OPENCLAW_TEST_RESULTS.md`
