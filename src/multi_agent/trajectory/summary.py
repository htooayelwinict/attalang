"""Trajectory summarization for embedding generation.

Formats trajectory data into text summaries suitable for graph RAG
embedding and semantic search over past agent executions.
"""

from src.multi_agent.trajectory.models import TrajectoryRecord


def summarize_trajectory(record: TrajectoryRecord) -> str:
    """Create text summary of a trajectory for embedding.

    Format: "task -> docker cmd1 -> docker cmd2 -> ... -> outcome"
    Includes docker_cli arg expansion for richer semantic signal.

    Args:
        record: Complete trajectory record

    Returns:
        Text summary (max 800 chars)
    """
    parts: list[str] = [record.task]

    for tc in record.tool_calls:
        if tc.docker_cli_args:
            parts.append(tc.docker_cli_args.full_command)
        else:
            label = tc.tool
            if tc.input_parsed:
                arg_preview = ", ".join(
                    f"{k}={str(v)[:40]}" for k, v in list(tc.input_parsed.items())[:3]
                )
                label = f"{tc.tool}({arg_preview})"
            parts.append(label)

    m = record.metrics
    if m.total_tool_calls > 0:
        rate = m.successful_tool_calls / m.total_tool_calls
        if rate >= 1.0:
            parts.append("success")
        elif rate >= 0.5:
            parts.append(f"partial ({m.successful_tool_calls}/{m.total_tool_calls})")
        else:
            parts.append(f"failed ({m.successful_tool_calls}/{m.total_tool_calls})")
    else:
        parts.append("no tools executed")

    if m.loop_detected:
        parts.append("LOOP_DETECTED")

    if m.total_tokens > 0:
        parts.append(f"tokens={m.total_tokens}")

    summary = " -> ".join(parts)
    if len(summary) > 800:
        summary = summary[:797] + "..."
    return summary


def trajectory_to_dict(record: TrajectoryRecord) -> dict:
    """Serialize a TrajectoryRecord to a plain dict for storage.

    Uses Pydantic's model_dump with mode="json" for JSON-safe output.
    Suitable for Qdrant payload, JSONL logs, or graph RAG nodes.
    """
    return record.model_dump(mode="json")
