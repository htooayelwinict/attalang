# Code Standards

## General Principles

1. Follow existing patterns in the codebase
2. Line length: 100 chars
3. Python: 3.11+ with modern type syntax (`str | None`, `list[dict]`)
4. Double quotes for strings
5. Tool results return `dict` with `success` field - never raise

## Project Structure

| Directory | Purpose |
|-----------|---------|
| `src/multi_agent/` | V1 LangGraph implementation |
| `src/multi_agent_v2/` | V2 Pydantic implementation |
| `src/multi_agent_v3/` | V3 Programmatic (code execution) |
| `src/skills/` | Agent skill definitions (SKILL.md) |
| `tests/` | Pytest test files |

## Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Agent classes | PascalCase + Agent/AgentV2 | `DockerAgent`, `DockerAgentV2` |
| Runtime classes | PascalCase + Runtime | `DockerGraphRuntime`, `DockerRuntimeV2` |
| Tool functions | snake_case | `list_containers`, `run_container` |
| CLI modules | cli.py / cli_v2.py | `cli.py`, `cli_v2.py` |
| Skills dirs | kebab-case | `docker-management-v2` |

## Tool Implementation Pattern

```python
def list_containers(all: bool = False) -> dict[str, Any]:
    """List Docker containers."""
    try:
        client = docker.from_env()
        containers = client.containers.list(all=all)
        return {
            "success": True,
            "containers": [
                {"name": c.name, "status": c.status, "image": c.image.tags[0]}
                for c in containers
            ]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
```

**Rules:**
- Never raise exceptions - return error dict
- Always include `success: bool` field
- Use type hints on all functions

## V2 Tool Wrapper Pattern

V2 tools need `RunContext` as first parameter:

```python
from pydantic_ai import RunContext

def _wrap_tool_for_context(fn: Any) -> Any:
    """Wrap function to accept RunContext."""
    @functools.wraps(fn)
    def wrapper(ctx: RunContext[Any], *args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper
```

## V3 Programmatic Pattern

V3 uses code execution instead of direct tool calls:

```python
# LLM generates Python code
code = '''
result = docker_cli(command="ps", args="-a")
print(result)
'''

# CodeExecutor runs it in restricted sandbox
executor = CodeExecutor(tool_namespace=bridge.make_namespace())
output = executor.execute(code)
```

**Rules:**
- Always use keyword arguments: `docker_cli(command="ps", args="-a")`
- Use `print()` to see results - only printed output is returned
- Shell operators blocked: `; | && || ` $(`
- Available imports: json, re, time, textwrap, itertools, functools, collections
- No file I/O, no subprocess, no network calls

## Testing

```bash
# Run all tests
.venv/bin/python -m pytest tests/

# Run specific file
.venv/bin/python -m pytest tests/test_docker_agent_v2.py

# With coverage
.venv/bin/python -m pytest --cov=src --cov-report=term-missing
```

## Linting & Formatting

```bash
ruff check src/ --fix    # Lint + fix
ruff format src/         # Format
mypy src/                # Type check
```

## CLI Pattern (Click)

```python
import click

@click.command()
@click.option("--model", default=None, help="Model name")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
def main(model: str | None, verbose: bool) -> None:
    """CLI entrypoint."""
    if verbose:
        for event in runtime.run_turn_verbose(prompt, thread_id):
            click.echo(event)
    else:
        click.echo(runtime.run_turn(prompt, thread_id))
```

## Environment Variables

| Variable | Required | Default |
|----------|----------|---------|
| `OPENROUTER_API_KEY` | Yes | - |
| `OPENROUTER_MODEL` | No | `openai/gpt-4o-mini` |
| `MULTI_AGENT_DOCKER_WORKSPACE` | No | `/tmp/multi-agent-docker-workspace` |
| `MULTI_AGENT_DOCKER_V2_WORKSPACE` | No | `/tmp/multi-agent-docker-v2-workspace` |
| `PROGRAMMATIC_TIMEOUT_SECONDS` | No | `120` |
| `PROGRAMMATIC_MAX_OUTPUT_CHARS` | No | `8000` |

## Security Patterns

- `.env` in `.gitignore` (never commit secrets)
- Docker tools use `docker.from_env()` - no host execution
- Skills loaded into virtual filesystem
- Workspace isolation per thread
- **V3**: Shell operators blocked in docker_cli args (`; | && || ` $( `)
