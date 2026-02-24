"""Trajectory collection for Docker agent tool calls and LLM interactions.

Captures structured records of every tool invocation (with expanded args),
LLM calls, timing, success/failure, and loop detection for future
graph RAG feedback loops and sandbox orchestrator integration.
"""

from src.multi_agent.trajectory.collector import TrajectoryCollector
from src.multi_agent.trajectory.models import (
    LLMCallRecord,
    ToolCallRecord,
    TrajectoryMetrics,
    TrajectoryRecord,
)
from src.multi_agent.trajectory.summary import summarize_trajectory

__all__ = [
    "TrajectoryCollector",
    "LLMCallRecord",
    "ToolCallRecord",
    "TrajectoryMetrics",
    "TrajectoryRecord",
    "summarize_trajectory",
]
