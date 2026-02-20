---
name: docker-management
description: Route Docker tasks to appropriate subagents.
---

# Docker Routing

Route tasks to subagents with the `task` tool:

| Task Type | Subagent |
|-----------|----------|
| Containers (run, stop, logs, exec, inspect) | container-agent |
| Images (pull, build, tag, prune) | image-agent |
| Networks | network-agent |
| Volumes | volume-agent |
| Docker Compose | compose-agent |
| System (info, prune, version) | system-agent |

## Examples

- `task("list all containers", "container-agent")`
- `task("pull nginx:latest", "image-agent")`
- `task("show docker version", "system-agent")`
