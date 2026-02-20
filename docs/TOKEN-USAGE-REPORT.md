# Token Usage Report - Docker Agent (Subagent Architecture)

**Date:** 2026-02-21

## Summary

| Metric | Before (Direct Tools) | After (Subagents) | Delta |
|--------|------------------------|-------------------|-------|
| Main agent direct tools | 35 | 0 | -100% |
| Subagents | 0 | 6 | +6 |
| Your content tokens (sys + tools + skills + subagent descs) | ~5,403 | 471 | -91.3% |
| Estimated total input tokens | ~22,600 | ~6,371 | **-71.8%** |

## Measured After State

Measured with local script on 2026-02-21:

- `system_prompt`: `199`
- `direct_tools`: `0`
- `skills`: `154`
- `subagent_descriptions`: `118`
- `your_content_total`: `471`
- estimated DeepAgents overhead: `~5,900`
- **estimated total**: `~6,371`

## Subagent Layout

| Subagent | Tool Count | Domain |
|----------|------------|--------|
| `container-agent` | 10 | container lifecycle + logs/stats/exec |
| `image-agent` | 7 | pull/build/tag/remove/inspect/prune |
| `network-agent` | 6 | create/connect/disconnect/remove/inspect |
| `volume-agent` | 5 | create/remove/inspect/prune |
| `compose-agent` | 4 | compose up/down/ps/logs |
| `system-agent` | 3 | info/prune/version |

## Why This Drops Tokens

- Main coordinator no longer carries all tool schemas.
- Tool schemas are isolated to subagents and loaded only when delegated.
- Skills file was reduced to routing-only guidance.

## Verification Commands

```bash
# Architecture check
.venv/bin/python -c "from src.multi_agent.agents import DockerAgent; a=DockerAgent(); print(len(a._tools), len(a._subagents))"

# Token check
.venv/bin/python - <<'PY'
from pathlib import Path
import json
import tiktoken
from src.multi_agent.agents import DockerAgent

enc = tiktoken.encoding_for_model('gpt-4')
a = DockerAgent()

sys_tokens = len(enc.encode(a._instructions))
tool_tokens = 0
skill_tokens = sum(len(enc.encode(p.read_text())) for p in Path('src/skills').rglob('*.md'))
subagent_desc_tokens = sum(len(enc.encode(f"{s['name']}: {s['description']}")) for s in a._subagents)

print('your_content', sys_tokens + tool_tokens + skill_tokens + subagent_desc_tokens)
print('estimated_total', sys_tokens + tool_tokens + skill_tokens + subagent_desc_tokens + 5900)
PY
```

## Notes

- Absolute token totals vary by model/provider formatting.
- The structural improvement target (`tools=0`, `subagents=6`) is satisfied.
