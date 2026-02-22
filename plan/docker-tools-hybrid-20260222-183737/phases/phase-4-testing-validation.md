# Phase 4: Testing and Validation

## Objective
Validate token reduction, verify all functionality works, and ensure HITL security is maintained.

## Prerequisites
- Phases 1-3 complete

## Tasks

- [ ] Create token comparison test script
- [ ] Run baseline token measurement (before migration)
- [ ] Run post-migration token measurement
- [ ] Verify 70%+ reduction achieved
- [ ] Run full test suite
- [ ] Manual integration testing
- [ ] HITL security testing
- [ ] Document results in plan

## Files to Create/Modify

| File | Action | Details |
|------|--------|---------|
| `tests/test_token_reduction.py` | Create | Token comparison tests |
| `tests/test_docker_bash.py` | Create | Bash tool unit tests |

## Test Cases

### Token Comparison Test
```python
# tests/test_token_reduction.py
import tiktoken
from src.multi_agent.tools.docker_tools import (
    list_containers, get_container_logs, start_container,
    list_images, docker_system_info
)

def count_tokens(text: str) -> int:
    enc = tiktoken.encoding_for_model("gpt-4")
    return len(enc.encode(text))

def test_list_containers_token_reduction():
    """Verify list_containers uses fewer tokens."""
    result = list_containers(all_containers=True)
    tokens = count_tokens(result)
    # Before: ~200-300 tokens
    # After: ~50-80 tokens
    assert tokens < 100, f"Expected <100 tokens, got {tokens}"

def test_get_container_logs_token_reduction():
    """Verify get_container_logs uses fewer tokens."""
    # Requires running container
    result = get_container_logs("nginx", tail=100)
    tokens = count_tokens(result)
    # Before: ~150-250 tokens
    # After: ~30-50 tokens
    assert tokens < 80, f"Expected <80 tokens, got {tokens}"
```

### Bash Tool Unit Tests
```python
# tests/test_docker_bash.py
import pytest
from src.multi_agent.tools.docker_tools import docker_bash, _validate_docker_command

def test_docker_bash_ps():
    result = docker_bash("ps")
    assert "success" in result.lower() or "container" in result.lower()

def test_docker_bash_images():
    result = docker_bash("images")
    assert "success" in result.lower() or "image" in result.lower()

def test_docker_bash_rejects_dangerous():
    """Dangerous commands must be rejected."""
    with pytest.raises(ValueError):
        _validate_docker_command("rm container1")

    with pytest.raises(ValueError):
        _validate_docker_command("rmi nginx")

    with pytest.raises(ValueError):
        _validate_docker_command("system prune")

def test_docker_bash_rejects_non_docker():
    """Non-docker commands must be rejected."""
    with pytest.raises(ValueError):
        _validate_docker_command("ls -la")

    with pytest.raises(ValueError):
        _validate_docker_command("rm -rf /")
```

### HITL Security Test
```python
def test_dangerous_tools_require_approval():
    """Verify dangerous tools still trigger HITL."""
    from src.multi_agent.agents.docker_agent import DANGEROUS_TOOLS, AUTO_REJECT_TOOLS

    assert "remove_image" in DANGEROUS_TOOLS
    assert "prune_images" in DANGEROUS_TOOLS
    assert "remove_volume" in AUTO_REJECT_TOOLS
    assert "prune_volumes" in AUTO_REJECT_TOOLS
    assert "docker_system_prune" in AUTO_REJECT_TOOLS
```

## Verification Commands
```bash
# Run all tests
.venv/bin/python -m pytest tests/ -v

# Run specific token tests
.venv/bin/python -m pytest tests/test_token_reduction.py -v

# Manual token comparison
.venv/bin/python -c "
from src.multi_agent.tools.docker_tools import list_containers
result = list_containers()
print(f'Chars: {len(result)}')
print(f'Est. tokens: {len(result)//4}')
print('---')
print(result[:500])
"

# Integration test with CLI
.venv/bin/python -m src.multi_agent.runtime.cli --prompt "list all containers"

# HITL test (should prompt)
.venv/bin/python -m src.multi_agent.runtime.cli --prompt "remove nginx image"
```

## Success Criteria

| Metric | Target | Verification |
|--------|--------|--------------|
| Token reduction | 70%+ | test_token_reduction.py passes |
| All tests pass | 100% | pytest returns 0 |
| HITL intact | Yes | test_dangerous_tools_require_approval passes |
| No breaking changes | Yes | Manual CLI testing |

## Estimated Effort
**2-3 hours (S)**

## Deliverables
- Token comparison tests
- Bash tool unit tests
- Test results documented
- Success criteria verified
