"""Trajectory collector callback handler for LangChain agents.

Captures structured tool call records with full argument decomposition
(especially docker_cli), LLM calls, timing, and loop detection.
Thread-safe for concurrent agent executions.
"""

import ast
import json
import logging
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from src.multi_agent.trajectory.models import (
    DockerCliArgs,
    LLMCallRecord,
    ToolCallRecord,
    TrajectoryMetrics,
    TrajectoryRecord,
)

logger = logging.getLogger("src.multi_agent.trajectory")


class TrajectoryCollector(BaseCallbackHandler):
    """Callback handler that captures structured trajectory data.

    Designed for the Docker agent — expands docker_cli args into structured
    fields for downstream graph RAG ingestion and sandbox orchestration.

    Usage:
        collector = TrajectoryCollector()
        response = agent.invoke(message, callbacks=[collector])
        record = collector.finalize("user task", thread_id="abc")
        # record is a TrajectoryRecord with all tool_calls, llm_calls, metrics
    """

    # Single pattern to redact credential values before storage.
    # Matches key=value or key: value where key looks like a secret name.
    _REDACT_RE: re.Pattern[str] = re.compile(
        r"(?P<key>"
        # Explicit env var names
        r"POSTGRES_PASSWORD|MYSQL_ROOT_PASSWORD|REDIS_PASSWORD|SECRET_KEY"
        r"|"
        # Generic secret-sounding keys
        r"(?:[\w]*(?:password|passwd|secret|token|api_key|apikey|auth|credential)[\w]*)"
        r")"
        r"(?P<sep>[=:])\s*"
        r"(?P<val>[^\s,;\n\]}{\"']{3,})",
        re.IGNORECASE,
    )

    def __init__(self, max_repeated_calls: int = 5, redact: bool = True) -> None:
        self._lock = threading.Lock()
        self._tool_calls: list[ToolCallRecord] = []
        self._llm_calls: list[LLMCallRecord] = []
        self._pending_tools: dict[str, dict[str, Any]] = {}  # run_id -> start data
        self._pending_llms: dict[str, dict[str, Any]] = {}  # run_id -> start data
        self._sequence_counter = 0
        self._loop_detected = False
        self._consecutive_empty = 0
        self._same_tool_streak: dict[str, Any] = {"tool": None, "count": 0}
        self._max_repeated_calls = max_repeated_calls
        self._redact = redact
        self._started_at: datetime | None = None

    # ── tool lifecycle ──────────────────────────────────────────────

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
        # Record session start on first tool call
        if self._started_at is None:
            self._started_at = datetime.now(timezone.utc)

        tool_name = serialized.get("name", "unknown")
        parsed = self._parse_input(input_str)
        docker_args = self._expand_docker_cli(parsed) if tool_name == "docker_cli" else None

        with self._lock:
            seq = self._sequence_counter
            self._sequence_counter += 1
            self._pending_tools[str(run_id)] = {
                "tool": tool_name,
                "input_raw": input_str,
                "input_parsed": parsed,
                "docker_cli_args": docker_args,
                "start_time": time.time(),
                "sequence": seq,
            }

        logger.debug("tool_start seq=%d tool=%s input=%s", seq, tool_name, parsed)

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        with self._lock:
            pending = self._pending_tools.pop(str(run_id), None)
            if pending is None:
                logger.warning("orphaned tool_end run_id=%s", run_id)
                return

            end_time = time.time()
            latency = end_time - pending["start_time"]
            is_error = self._is_error_output(output)
            is_empty = self._is_empty_output(output)
            success = not (is_error or is_empty)

            record = ToolCallRecord(
                tool=pending["tool"],
                input_raw=pending["input_raw"],
                input_parsed=pending["input_parsed"],
                docker_cli_args=pending["docker_cli_args"],
                output=str(output)[:4000] if output else None,
                success=success,
                error=str(output)[:500] if is_error else None,
                start_time=pending["start_time"],
                end_time=end_time,
                latency=latency,
                run_id=str(run_id),
                sequence=pending["sequence"],
            )
            self._tool_calls.append(record)

            # loop detection
            self._update_loop_detection(pending["tool"], is_empty, pending["input_parsed"])

        logger.debug(
            "tool_end seq=%d tool=%s success=%s latency=%.2fs",
            record.sequence, record.tool, success, latency,
        )

    def on_tool_error(
        self,
        error: Exception,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        with self._lock:
            pending = self._pending_tools.pop(str(run_id), None)
            if pending is None:
                logger.warning("orphaned tool_error run_id=%s", run_id)
                return

            end_time = time.time()
            latency = end_time - pending["start_time"]

            record = ToolCallRecord(
                tool=pending["tool"],
                input_raw=pending["input_raw"],
                input_parsed=pending["input_parsed"],
                docker_cli_args=pending["docker_cli_args"],
                output=None,
                success=False,
                error=str(error)[:500],
                start_time=pending["start_time"],
                end_time=end_time,
                latency=latency,
                run_id=str(run_id),
                sequence=pending["sequence"],
            )
            self._tool_calls.append(record)

        logger.debug("tool_error seq=%d tool=%s error=%s", record.sequence, record.tool, error)

    # ── LLM lifecycle ───────────────────────────────────────────────

    def on_llm_start(
        self,
        serialized: dict[str, Any] | None,
        prompts: list[str],
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        model = (serialized or {}).get("name", "unknown")
        with self._lock:
            self._pending_llms[str(run_id)] = {
                "model": model,
                "start_time": time.time(),
            }

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        model = serialized.get("name", serialized.get("id", ["unknown"])[-1])
        with self._lock:
            self._pending_llms[str(run_id)] = {
                "model": str(model),
                "start_time": time.time(),
            }

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        with self._lock:
            pending = self._pending_llms.pop(str(run_id), None)
            if pending is None:
                return

            end_time = time.time()
            latency = end_time - pending["start_time"]

            token_usage: dict[str, int] = {}
            if response.llm_output and isinstance(response.llm_output, dict):
                raw = response.llm_output.get("token_usage", {})
                if isinstance(raw, dict):
                    token_usage = {k: int(v) for k, v in raw.items() if isinstance(v, (int, float))}

            record = LLMCallRecord(
                model=pending["model"],
                start_time=pending["start_time"],
                end_time=end_time,
                latency=latency,
                token_usage=token_usage,
                run_id=str(run_id),
            )
            self._llm_calls.append(record)

    # ── finalization ────────────────────────────────────────────────

    def finalize(
        self,
        task: str,
        thread_id: str | None = None,
        success: bool = True,
        error: str | None = None,
    ) -> TrajectoryRecord:
        """Build the final TrajectoryRecord from collected data.

        Call once after agent.invoke() completes.

        Note: loop_detected is recorded in metrics but does NOT override
        the caller-provided success flag. The caller (or a downstream
        scorer) decides whether a loop constitutes failure.
        """
        completed_at = datetime.now(timezone.utc)
        with self._lock:
            started_at = self._started_at or completed_at
            metrics = self._compute_metrics()
            redacted_task = self._redact_string(task) if self._redact else task
            tool_calls = self._redact_tool_calls(list(self._tool_calls)) if self._redact else list(self._tool_calls)
            record = TrajectoryRecord(
                task=redacted_task,
                thread_id=thread_id,
                tool_calls=tool_calls,
                llm_calls=list(self._llm_calls),
                metrics=metrics,
                started_at=started_at,
                completed_at=completed_at,
                success=success,
                error=error,
            )
        return record

    def clear(self) -> None:
        """Reset all state for reuse across turns."""
        with self._lock:
            self._tool_calls.clear()
            self._llm_calls.clear()
            self._pending_tools.clear()
            self._pending_llms.clear()
            self._sequence_counter = 0
            self._loop_detected = False
            self._consecutive_empty = 0
            self._same_tool_streak = {"tool": None, "count": 0}
            self._started_at = None

    @property
    def loop_detected(self) -> bool:
        with self._lock:
            return self._loop_detected

    @property
    def tool_calls(self) -> list[ToolCallRecord]:
        with self._lock:
            return list(self._tool_calls)

    @property
    def llm_calls(self) -> list[LLMCallRecord]:
        with self._lock:
            return list(self._llm_calls)

    # ── internal helpers ────────────────────────────────────────────

    @staticmethod
    def _parse_input(input_str: str) -> dict[str, Any]:
        """Parse tool input string to dict.

        LangChain may pass JSON ('{"command": "ps"}') or Python repr
        ("{'command': 'ps'}"). We try json.loads first, then fall back
        to ast.literal_eval for the repr case.
        """
        if not input_str:
            return {}
        # Try JSON first
        try:
            parsed = json.loads(input_str)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except (json.JSONDecodeError, TypeError):
            pass
        # Fallback: Python repr (single-quoted dicts from LangChain)
        try:
            parsed = ast.literal_eval(input_str)
            if isinstance(parsed, dict):
                return parsed
            return {"value": parsed}
        except (ValueError, SyntaxError):
            pass
        return {"raw": input_str}

    @staticmethod
    def _expand_docker_cli(parsed: dict[str, Any]) -> DockerCliArgs | None:
        """Expand docker_cli parsed args into structured DockerCliArgs."""
        command = parsed.get("command")
        if command is None:
            return None

        args = parsed.get("args")
        cwd = parsed.get("cwd")
        timeout = parsed.get("timeout")

        # Reconstruct full command
        parts = ["docker", str(command)]
        if args:
            parts.append(str(args))
        full_command = " ".join(parts)

        return DockerCliArgs(
            command=str(command),
            args=str(args) if args else None,
            cwd=str(cwd) if cwd else None,
            timeout=int(timeout) if timeout is not None else None,
            full_command=full_command,
        )

    @staticmethod
    def _is_error_output(output: Any) -> bool:
        if not output:
            return False
        text = str(output).lower()
        return any(p in text for p in (
            "error:", "error (exit", "failed", "timeout",
            '"success": false', "'success': false",
        ))

    @staticmethod
    def _is_empty_output(output: Any) -> bool:
        if output is None:
            return True
        text = str(output).strip()
        return not text or text in ("none", "null", "[]", "{}")

    def _update_loop_detection(
        self, tool_name: str, is_empty: bool, input_parsed: dict[str, Any]
    ) -> None:
        """Track loop patterns. Sets _loop_detected but does NOT raise."""
        if is_empty:
            self._consecutive_empty += 1
        else:
            self._consecutive_empty = 0

        if tool_name == self._same_tool_streak["tool"]:
            self._same_tool_streak["count"] += 1
        else:
            self._same_tool_streak = {"tool": tool_name, "count": 1}

        # Check patterns
        if self._consecutive_empty >= self._max_repeated_calls:
            self._loop_detected = True
            logger.warning(
                "loop detected: %d consecutive empty results from %s",
                self._consecutive_empty, tool_name,
            )

        if self._same_tool_streak["count"] >= self._max_repeated_calls + 1:
            self._loop_detected = True
            logger.warning(
                "loop detected: %s called %d times consecutively",
                tool_name, self._same_tool_streak["count"],
            )

        # Check identical calls in last N
        recent = self._tool_calls[-(self._max_repeated_calls):]
        if len(recent) >= self._max_repeated_calls:
            tools = [r.tool for r in recent]
            inputs = [json.dumps(r.input_parsed, sort_keys=True)[:200] for r in recent]
            if len(set(tools)) == 1 and len(set(inputs)) == 1:
                self._loop_detected = True
                logger.warning(
                    "loop detected: identical calls to %s repeated %d times",
                    tool_name, self._max_repeated_calls,
                )

    @classmethod
    def _redact_string(cls, text: str) -> str:
        """Replace credential values with [REDACTED] in a string."""
        def _sub(m: re.Match[str]) -> str:
            return f"{m.group('key')}{m.group('sep')}[REDACTED]"
        return cls._REDACT_RE.sub(_sub, text)

    @classmethod
    def _redact_dict(cls, d: dict[str, Any]) -> dict[str, Any]:
        """Recursively redact credential values in a dict."""
        out: dict[str, Any] = {}
        for k, v in d.items():
            if isinstance(v, str):
                out[k] = cls._redact_string(v)
            elif isinstance(v, dict):
                out[k] = cls._redact_dict(v)
            else:
                out[k] = v
        return out

    @classmethod
    def _redact_tool_calls(cls, calls: list[ToolCallRecord]) -> list[ToolCallRecord]:
        """Return a new list of ToolCallRecords with credentials redacted."""
        redacted: list[ToolCallRecord] = []
        for tc in calls:
            redacted_input_raw = cls._redact_string(tc.input_raw)
            redacted_parsed = cls._redact_dict(tc.input_parsed)
            redacted_output = cls._redact_string(tc.output) if tc.output else tc.output
            redacted_error = cls._redact_string(tc.error) if tc.error else tc.error

            redacted_docker_args = None
            if tc.docker_cli_args:
                redacted_docker_args = DockerCliArgs(
                    command=tc.docker_cli_args.command,
                    args=cls._redact_string(tc.docker_cli_args.args) if tc.docker_cli_args.args else tc.docker_cli_args.args,
                    cwd=tc.docker_cli_args.cwd,
                    timeout=tc.docker_cli_args.timeout,
                    full_command=cls._redact_string(tc.docker_cli_args.full_command),
                )

            redacted.append(ToolCallRecord(
                tool=tc.tool,
                input_raw=redacted_input_raw,
                input_parsed=redacted_parsed,
                docker_cli_args=redacted_docker_args,
                output=redacted_output,
                success=tc.success,
                error=redacted_error,
                start_time=tc.start_time,
                end_time=tc.end_time,
                latency=tc.latency,
                run_id=tc.run_id,
                sequence=tc.sequence,
            ))
        return redacted

    def _compute_metrics(self) -> TrajectoryMetrics:
        completed = [tc for tc in self._tool_calls if tc.end_time is not None]
        latencies = [tc.latency for tc in completed if tc.latency is not None]
        successful = [tc for tc in completed if tc.success]
        failed = [tc for tc in completed if not tc.success]

        total_tokens = 0
        prompt_tokens = 0
        completion_tokens = 0
        for llm in self._llm_calls:
            total_tokens += llm.token_usage.get("total_tokens", 0)
            prompt_tokens += llm.token_usage.get("prompt_tokens", 0)
            completion_tokens += llm.token_usage.get("completion_tokens", 0)

        # Collect unique docker commands
        docker_commands: list[str] = []
        seen: set[str] = set()
        for tc in self._tool_calls:
            if tc.docker_cli_args and tc.docker_cli_args.command not in seen:
                seen.add(tc.docker_cli_args.command)
                docker_commands.append(tc.docker_cli_args.command)

        return TrajectoryMetrics(
            total_tool_calls=len(completed),
            successful_tool_calls=len(successful),
            failed_tool_calls=len(failed),
            total_latency=sum(latencies) if latencies else 0.0,
            avg_latency=(sum(latencies) / len(latencies)) if latencies else 0.0,
            total_llm_calls=len(self._llm_calls),
            total_tokens=total_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            loop_detected=self._loop_detected,
            docker_commands_used=docker_commands,
        )
