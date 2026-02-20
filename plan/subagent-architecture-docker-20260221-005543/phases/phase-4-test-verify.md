# Phase 4: Test & Verify

## Objective
Confirm token reduction and functionality.

## Prerequisites
- Phases 1-3 completed

## Tasks

### 4.1 Token calculation
- [ ] Run token calculation script
- [ ] Verify main agent tokens reduced by 40%+

```bash
source .venv/bin/activate && python3 << 'EOF'
import tiktoken
from src.multi_agent.agents import DockerAgent
from pathlib import Path
import json

enc = tiktoken.encoding_for_model("gpt-4")
agent = DockerAgent()

# System prompt
sys_tokens = len(enc.encode(agent._instructions))

# Tools (should be 0)
tool_tokens = sum(len(enc.encode(json.dumps({"name": t.name, "desc": t.description, "schema": t.args_schema.model_json_schema() if t.args_schema else {}}))) for t in agent._tools)

# Skills
skill_tokens = sum(len(enc.encode(p.read_text())) for p in Path("src/skills").rglob("*.md"))

# Subagent descriptions (what main agent sees)
subagent_desc_tokens = sum(len(enc.encode(f"{s['name']}: {s['description']}")) for s in agent._subagents)

print("=" * 50)
print("TOKEN ANALYSIS")
print("=" * 50)
print(f"System Prompt:      {sys_tokens:>6}")
print(f"Direct Tools:       {tool_tokens:>6} (should be 0)")
print(f"Skills:             {skill_tokens:>6}")
print(f"Subagent Descs:     {subagent_desc_tokens:>6}")
print("-" * 50)
your_content = sys_tokens + tool_tokens + skill_tokens + subagent_desc_tokens
print(f"YOUR CONTENT:       {your_content:>6}")
print(f"DeepAgents (~5900): ~5900")
print("-" * 50)
print(f"ESTIMATED TOTAL:    {your_content + 5900:>6}")
print("=" * 50)
print(f"\nTARGET: ~6,500 tokens")
EOF
```

### 4.2 Functional tests
- [ ] Test single operation
- [ ] Test multi-group operation

```bash
# Test 1: Single container operation
multi-agent-cli --prompt "list my docker containers"

# Test 2: Image operation
multi-agent-cli --prompt "list available images"

# Test 3: System info
multi-agent-cli --prompt "show docker version"
```

### 4.3 Verify LangSmith trace
- [ ] Run test query
- [ ] Check LangSmith for input token count
- [ ] Should show ~6,500 tokens (not ~11,300)

### 4.4 Update documentation
- [ ] Update TOKEN-USAGE-REPORT.md

```markdown
## After Subagent Architecture

| Component | Tokens |
|-----------|--------|
| System Prompt | ~150 |
| Direct Tools | 0 |
| Skills | ~50 |
| Subagent Descriptions | ~112 |
| DeepAgents Overhead | ~5,900 |
| **TOTAL** | **~6,500** |

**Savings: 43% reduction (11,300 → 6,500)**
```

## Files
| File | Action |
|------|--------|
| `docs/TOKEN-USAGE-REPORT.md` | Update with new metrics |

## Success Criteria
- [ ] Main agent tools = 0
- [ ] Subagents = 6
- [ ] Input tokens < 7,000
- [ ] All functional tests pass
- [ ] LangSmith confirms reduction

## Estimate
1 hour (S)
