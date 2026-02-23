"""Verbose callback handler for showing real-time agent activity.

Similar to sample-srcs/bot pattern - shows tool calls, LLM activity, and results.
"""

import click
from typing import Any, Optional

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult


class VerboseCallback(BaseCallbackHandler):
    """Callback handler for verbose real-time output of agent activity."""

    def __init__(self, show_tool_output: bool = True, truncate_at: int = 600) -> None:
        """Initialize verbose callback.

        Args:
            show_tool_output: Whether to show tool results (default: True)
            truncate_at: Truncate tool output at this length (default: 600)
        """
        self.show_tool_output = show_tool_output
        self.truncate_at = truncate_at
        self._tool_start_time: dict[str, float] = {}

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Show tool call with input parameters."""
        import time
        tool_name = serialized.get("name", "unknown")
        self._tool_start_time[tool_name] = time.time()

        click.secho(f"\n🔧 Tool: {tool_name}", fg="cyan", bold=True)

        # Pretty print tool input
        try:
            import json
            if isinstance(input_str, str):
                try:
                    parsed = json.loads(input_str)
                    if isinstance(parsed, dict):
                        for k, v in parsed.items():
                            value_str = str(v)[:100] + "..." if len(str(v)) > 100 else str(v)
                            click.echo(f"   {k}: {value_str}")
                    else:
                        click.echo(f"   {input_str[:200]}")
                except json.JSONDecodeError:
                    click.echo(f"   {input_str[:200]}")
            else:
                click.echo(f"   {input_str[:200]}")
        except Exception:
            click.echo(f"   {input_str[:200]}")

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Show tool result with timing."""
        import time

        # Find tool name from context (we stored start time)
        tool_name = "unknown"
        for tn, start_time in list(self._tool_start_time.items()):
            if time.time() - start_time < 60:  # Started within last minute
                tool_name = tn
                del self._tool_start_time[tn]
                break

        if not self.show_tool_output:
            return

        # Check for errors
        output_str = str(output)
        is_error = any(e in output_str.lower() for e in ["error:", "failed", "timeout"])
        status = "❌" if is_error else "✅"

        click.secho(f"{status} Tool result: {tool_name}", fg="yellow")

        # Truncate long output
        if len(output_str) > self.truncate_at:
            click.echo(output_str[:self.truncate_at])
            click.echo(f"\n... ({len(output_str) - self.truncate_at} more bytes)")
        else:
            click.echo(output_str)

    def on_tool_error(
        self,
        error: Exception,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Show tool error."""
        click.secho(f"❌ Tool Error: {error}", fg="red")

    def on_llm_start(
        self,
        serialized: dict[str, Any] | None,
        prompts: list[str],
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Show LLM call start (dim)."""
        if serialized is None:
            return
        model = serialized.get("name", "unknown") if serialized else "unknown"
        model_short = model.split("/")[-1]  # Get short model name
        click.secho(f"\n🧠 LLM: {model_short}", fg="blue", dim=True)

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Show LLM token usage if available."""
        if response.llm_output and isinstance(response.llm_output, dict):
            token_usage = response.llm_output.get("token_usage", {})
            if token_usage:
                total = token_usage.get("total_tokens", "?")
                click.secho(f"   Tokens: {total}", fg="blue", dim=True)

    def on_chat_model_start(
        self,
        serialized: dict[str, Any] | None,
        messages: list[list[BaseMessage]],
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Show chat model start (dim)."""
        if serialized is None:
            return
        model = serialized.get("name", "unknown") if serialized else "unknown"
        model_short = model.split("/")[-1] if model else "unknown"
        click.secho(f"\n🧠 Chat Model: {model_short}", fg="blue", dim=True)

    def on_chain_start(
        self,
        serialized: dict[str, Any] | None,
        inputs: dict[str, Any] | None,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Show chain/node start."""
        if serialized is None:
            return
        name = serialized.get("name", "unknown") if serialized else "unknown"
        if name not in ["LangGraph", "DockerGraphRuntime", "__start__", "_start"]:  # Skip outer chains
            click.secho(f"\n▶️  Node: {name}", fg="blue", dim=True)

    def on_chain_end(
        self,
        outputs: dict[str, Any] | None,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Show chain/node end."""
        pass  # Too noisy to show every node end
