# Requirements Analysis: Subagent Architecture for Docker Tools

## Goal

Reduce input token usage from ~11,300 tokens to ~6,500 tokens by implementing subagent architecture that isolates tool groups.

## Current State

| Metric | Value |
|--------|-------|
| Input tokens | ~11,298 |
| System prompt | 125 tokens |
| Tools (37) | 4,924 tokens |
| Skills | 354 tokens |
| DeepAgents overhead | ~5,895 tokens |

## Target State

| Metric | Value |
|--------|-------|
| Main agent tokens | ~6,500 |
| Tool tokens in main | ~112 (subagent descriptions) |
| Savings | 43% reduction |

## Constraints

1. **SubAgents don't support `skills` parameter** - guidance must be embedded in `system_prompt`
2. **Must maintain all 37 tools functionality** - no feature regression
3. **Must work with DeepAgents framework** - use standard SubAgent schema
4. **Must support thread_id for conversation persistence**

## Acceptance Criteria

- [ ] Main agent input tokens reduced by 40%+
- [ ] All 6 tool groups accessible via subagents
- [ ] Single container query still works (e.g., "list containers")
- [ ] Multi-group operations work via task delegation
- [ ] LangSmith tracing shows token reduction

## Tool Groups

| Group | Tools | Tokens |
|-------|-------|--------|
| CONTAINER | 11 | 1,484 |
| IMAGE | 7 | 905 |
| NETWORK | 6 | 793 |
| VOLUME | 5 | 452 |
| COMPOSE | 4 | 1,066 |
| SYSTEM | 3 | 224 |

## Key Design Decisions

1. **Hybrid approach**: Main agent keeps minimal routing skill, subagents embed guidance in system_prompt
2. **No skills in subagents**: Use system_prompt for contextual guidance
3. **Tool isolation**: Each subagent only sees its tool group's schemas
