# Phase 3: Verify Token Reduction

## Objective
Confirm token reduction in LangSmith.

## Prerequisites
- Phases 1-2 completed

## Tasks

### 3.1 Run test queries
```bash
# Test 1: Simple list (should be <8k total)
multi-agent-cli --prompt "list containers"

# Test 2: Simple system query (should be <6k)
multi-agent-cli --prompt "docker version"

# Test 3: Multi-domain (should be <15k)
multi-agent-cli --prompt "pull nginx and run on 8080"
```

### 3.2 Check LangSmith traces
- Verify token counts dropped
- Compare to baseline (24k-41k)

### 3.3 Update documentation
- Update TOKEN-USAGE-REPORT.md with new metrics

## Success Criteria
| Query Type | Target | Baseline |
|------------|--------|----------|
| Simple (list/version) | <8k | 24k |
| Multi-domain | <15k | 41k |

## Verification Commands
```bash
# Check architecture still works
source .venv/bin/activate && python3 -c "
from src.multi_agent.agents import DockerAgent
a = DockerAgent()
print(f'Tools: {len(a._tools)}, Subagents: {len(a._subagents)}')
"
```

## Estimate
0.5 hour (XS)
