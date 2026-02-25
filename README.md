# AttaLang

Docker management agent with natural language interface. Three implementations: V1 (HITL security), V2 (Pydantic), V3 (programmatic code execution).

## Quick Start

```bash
# Clone and install
git clone https://github.com/htooayelwinict/attalang.git
cd attalang
python3 -m venv .venv
.venv/bin/pip install -e ".[dev,agentv2]"

# Configure
cp .env.example .env
# Edit .env and add OPENROUTER_API_KEY

# Run V1 with HITL security (recommended for production)
.venv/bin/python -m src.multi_agent.runtime.cli --hitl

# Run V2 (Pydantic) - verbose mode
.venv/bin/python -m src.multi_agent_v2.runtime.cli_v2 -v

# Run V3 (Programmatic) - token efficient + trajectory tracking
.venv/bin/python -m src.multi_agent_v3.runtime.cli_v3 -v
```

## Examples

```bash
# List containers
"show me all containers"

# Run nginx
"run nginx on port 8080"

# Multi-tier app
"create a network called app-net, then run nginx named web and redis named cache on that network"

# Cleanup
"stop and remove all containers"
```

## CLI Commands

```bash
# V1 (LangGraph) - with HITL security
multi-agent-cli --hitl                      # Interactive + security prompts
multi-agent-cli --prompt "list containers"  # Single-shot

# V2 (Pydantic)
multi-agent-cli-v2 -v                       # Verbose (shows tool calls)
multi-agent-cli-v2 --prompt "..."           # Single-shot

# V3 (Programmatic) - token efficient
multi-agent-cli-v3 -v                       # Verbose + trajectory tracking
multi-agent-cli-v3 --prompt "..."           # Single-shot
```

## Security

### V1: HITL (Human-in-the-Loop)

| Category | Tools | Behavior |
|----------|-------|----------|
| Safe | list_*, inspect_*, logs, stats | Execute directly |
| Dangerous | remove_image, prune_images | Prompt: "⚠️ Approve?" |
| Blocked | remove_volume, prune_*, system_prune | Auto-reject: "🚫 BLOCKED" |

```bash
# Enable HITL
multi-agent-cli --hitl

# Blocked operation (auto-rejected)
"remove the app-data volume"
🚫 BLOCKED: remove_volume - {'name': 'app-data'}
Operation remove_volume is not allowed.
```

### V3: Shell Operator Blocking

Blocks shell control operators in docker_cli args: `; | && || ` $(`

```bash
# Blocked
docker_cli(command="run", args="alpine sh -c 'cmd1 && cmd2'")

# Allowed - separate calls
docker_cli(command="exec", args="box cmd1")
docker_cli(command="exec", args="box cmd2")
```

## Documentation

| Doc | Description |
|-----|-------------|
| [Project Overview](docs/project-overview-pdr.md) | Goals, features, PDR |
| [Codebase Summary](docs/codebase-summary.md) | File structure and key files |
| [Code Standards](docs/code-standards.md) | Conventions and patterns |
| [System Architecture](docs/system-architecture.md) | Design and HITL flow |
| [Tool Prevention Patterns](docs/TOOL-PREVENTION-PATTERNS.md) | HITL security patterns |

## Tech Stack

| Component | V1 (LangChain) | V2 (Pydantic) | V3 (Programmatic) |
|-----------|----------------|---------------|-------------------|
| Framework | LangChain | Pydantic-AI | LangChain |
| Tool calling | Direct (N round-trips) | Prefixed (N round-trips) | **Code execution (1 script)** |
| Token efficiency | Normal | Normal | **High** |
| Security | HITL + auto-reject | - | Shell operator blocking |
| Research | - | - | Loop detection + trajectory |

## Development

```bash
# Run tests
.venv/bin/python -m pytest tests/

# Lint and format
ruff check src/ --fix && ruff format src/

# Type check
mypy src/
```

## Environment Variables

| Variable | Required | Default |
|----------|----------|---------|
| `OPENROUTER_API_KEY` | Yes | - |
| `OPENROUTER_MODEL` | No | `openai/gpt-4o-mini` |

## License

MIT
