# Phase 3: Simplify SKILL.md

## Objective
Convert current SKILL.md to minimal routing guidance.

## Prerequisites
- Phase 2 completed (DockerAgent updated)

## Tasks

### 3.1 Replace SKILL.md content
- [ ] Remove tool-specific guidance
- [ ] Keep only routing table
- [ ] Add task delegation examples

### Current Content (354 tokens)
```markdown
---
name: docker-management
description: Use this skill for Docker container, image, network, volume, compose, and diagnostics workflows.
---

# Docker Management
[Full scope, workflow, guardrails, workspace rules...]
```

### New Content (~50 tokens)
```markdown
---
name: docker-management
description: Route Docker tasks to appropriate subagents.
---

# Docker Routing

Route tasks to the appropriate subagent using the `task` tool:

| Task Type | Subagent |
|-----------|----------|
| Containers (run, stop, logs, exec) | container-agent |
| Images (pull, build, tag) | image-agent |
| Networks | network-agent |
| Volumes | volume-agent |
| Docker Compose | compose-agent |
| System (info, prune, version) | system-agent |

## Examples

- `task("list all containers", "container-agent")`
- `task("pull nginx image", "image-agent")`
- `task("show docker info", "system-agent")`
```

## Files
| File | Action |
|------|--------|
| `src/skills/docker-management/SKILL.md` | Replace content |

## Verification
```bash
source .venv/bin/activate && python3 -c "
from pathlib import Path
content = Path('src/skills/docker-management/SKILL.md').read_text()
import tiktoken
enc = tiktoken.encoding_for_model('gpt-4')
print(f'SKILL.md tokens: {len(enc.encode(content))}')
"
```

Expected: ~50 tokens (down from 354)

## Estimate
0.5 hour (XS)
