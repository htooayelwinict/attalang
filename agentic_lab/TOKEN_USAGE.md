# OpenClaw Token Usage Report

**Date:** 2025-02-22
**Model:** `qwen/qwen3-coder-next` (OpenRouter)

---

## OpenClaw Session Stats

| Metric | Value |
|--------|-------|
| **Sessions** | 1 |
| **Total Input Tokens** | 729 |
| **Total Output Tokens** | 228 |
| **Total Session Tokens** | 23,624 |
| **Context Window** | 200,000 |
| **Context Used** | 12% |
| **Model Provider** | openrouter |

---

## OpenRouter API Usage

| Period | Usage (USD) |
|--------|-------------|
| **Daily** | $0.10 |
| **Weekly** | $2.43 |
| **Monthly** | $2.98 |
| **Total (all time)** | $2.98 |

**API Key:** `sk-or-v1-85d...214`
**Label:** AttaLang DeepAgent
**Free Tier:** No

---

## Cost Breakdown by Test

| Test | Input | Output | Est. Cost |
|------|-------|--------|-----------|
| Simple query (2+2) | ~50 | ~20 | ~$0.001 |
| Docker list | ~100 | ~30 | ~$0.002 |
| Create nginx | ~150 | ~50 | ~$0.003 |
| Multi-stack deploy | ~429 | ~128 | ~$0.008 |

**Estimated total for tests:** ~$0.014

---

## Session Details

```
Session: agent:main:main
Kind: direct
Age: 4 minutes
Model: qwen3-coder-next
Provider: openrouter
System ID: 5d3c99a9-2b29-42a3-936e-b8d7ca218519
```

---

## Commands to Check Usage

```bash
# OpenClaw sessions
openclaw sessions
openclaw sessions --json

# OpenRouter API usage
curl -s "https://openrouter.ai/api/v1/auth/key" \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "HTTP-Referer: https://github.com/htooayelwinict/attalang" \
  -H "X-Title: AttaLang DeepAgent"
```

---

## Notes

- Session tokens include full conversation context (23,624 tokens)
- Only 957 tokens were actually consumed in our tests (729 input + 228 output)
- Remaining tokens are system prompt and context
- $2.98 monthly includes previous usage on this API key
