"""Pydantic models for trajectory collection.

Structured records for tool calls (with docker_cli arg expansion),
LLM interactions, metrics, and complete trajectory sessions.
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DockerCliArgs(BaseModel):
    """Expanded args for the docker_cli tool."""

    model_config = ConfigDict(extra="forbid")

    command: str = Field(description="Docker subcommand (ps, run, build, compose up, etc.)")
    args: str | None = Field(default=None, description="Additional CLI arguments")
    cwd: str | None = Field(default=None, description="Working directory")
    timeout: int | None = Field(default=None, description="Command timeout in seconds")
    full_command: str = Field(description="Reconstructed full docker command string")


class ToolCallRecord(BaseModel):
    """Single tool invocation record with timing and result."""

    model_config = ConfigDict(extra="forbid")

    tool: str = Field(description="Tool name")
    input_raw: str = Field(description="Raw input string from LangChain")
    input_parsed: dict[str, Any] = Field(
        default_factory=dict, description="Parsed input arguments"
    )
    docker_cli_args: DockerCliArgs | None = Field(
        default=None, description="Expanded docker_cli args (only for docker_cli tool)"
    )
    output: str | None = Field(default=None, description="Tool output")
    success: bool = Field(default=True, description="Whether the tool call succeeded")
    error: str | None = Field(default=None, description="Error message if failed")
    start_time: float = Field(description="Unix timestamp of tool start")
    end_time: float | None = Field(default=None, description="Unix timestamp of tool end")
    latency: float | None = Field(default=None, description="Execution time in seconds")
    run_id: str = Field(description="LangChain run ID")
    sequence: int = Field(description="Ordinal position in the trajectory (0-indexed)")


class LLMCallRecord(BaseModel):
    """Single LLM/chat model invocation record."""

    model_config = ConfigDict(extra="forbid")

    model: str = Field(default="unknown", description="Model name")
    start_time: float = Field(description="Unix timestamp")
    end_time: float | None = Field(default=None, description="Unix timestamp")
    latency: float | None = Field(default=None, description="Execution time in seconds")
    token_usage: dict[str, int] = Field(
        default_factory=dict, description="Token usage breakdown"
    )
    run_id: str = Field(description="LangChain run ID")


class TrajectoryMetrics(BaseModel):
    """Aggregated metrics for a trajectory session."""

    model_config = ConfigDict(extra="forbid")

    total_tool_calls: int = Field(default=0)
    successful_tool_calls: int = Field(default=0)
    failed_tool_calls: int = Field(default=0)
    total_latency: float = Field(default=0.0, description="Sum of all tool latencies")
    avg_latency: float = Field(default=0.0, description="Average tool latency")
    total_llm_calls: int = Field(default=0)
    total_tokens: int = Field(default=0)
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    loop_detected: bool = Field(default=False)
    docker_commands_used: list[str] = Field(
        default_factory=list, description="Unique docker subcommands used"
    )


class TrajectoryRecord(BaseModel):
    """Complete trajectory for a single agent turn."""

    model_config = ConfigDict(extra="forbid")

    task: str = Field(description="User input / task description")
    thread_id: str | None = Field(default=None, description="Conversation thread ID")
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    llm_calls: list[LLMCallRecord] = Field(default_factory=list)
    metrics: TrajectoryMetrics = Field(default_factory=TrajectoryMetrics)
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the turn started (set by collector on first tool call)",
    )
    completed_at: datetime | None = Field(default=None)
    success: bool = Field(default=True, description="Overall trajectory success")
    error: str | None = Field(default=None)
