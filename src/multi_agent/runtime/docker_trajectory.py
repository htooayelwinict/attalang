"""Docker-specific trajectory callback for loop detection and replan.

Detects Docker agent loops and triggers replan instead of hard abort.
"""

import json
import re
import threading
import time
from typing import Any, Optional

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


DOCKER_REPLAN_ALERT = """🚨 LOOP DETECTED - EXECUTION PAUSED

The following pattern suggests a stuck execution:

{loop_details}

INSTRUCTIONS:
1. STOP the current approach immediately
2. ANALYZE why this pattern is repeating
3. CREATE a different plan:
   - Check if resource already exists before creating
   - Try alternative parameters
   - Use different tool/commands
   - Ask user for clarification if stuck

DO NOT retry the same command with identical parameters.
"""


class DockerLoopException(Exception):
    """Raised when Docker loop is detected - triggers replan."""

    def __init__(self, message: str, loop_info: dict[str, Any]):
        super().__init__(message)
        self.loop_info = loop_info


class DockerTrajectoryCallback(BaseCallbackHandler):
    """Callback handler for Docker agent with loop detection and replan.

    Docker-specific patterns:
    - Container restart loops (start/stop same container repeatedly)
    - Resource creation conflicts (network/volume already exists)
    - Port binding retries (same port, same failure)
    - Image pull retries (pulling same image multiple times)
    - Identical command retries (same docker_cli command)
    """

    def __init__(self, max_retries: int = 3) -> None:
        """Initialize the Docker trajectory callback.

        Args:
            max_retries: Max identical calls before triggering replan (default: 3)
        """
        self.trajectory: list[dict[str, Any]] = []
        # Use RLock for reentrancy - get_trajectory() called while lock held
        self._lock = threading.RLock()
        self._loop_detected = False
        self._max_retries = max_retries

        # Tracking structures
        self._command_history: list[tuple[str, str]] = []  # (tool, input_hash)
        self._resource_attempts: dict[str, int] = {}  # resource_name -> attempt_count

        # Docker-specific counters
        self._container_ops: dict[str, int] = {}  # container_name -> op_count
        self._network_create_fails: dict[str, int] = {}  # network_name -> fail_count
        self._volume_create_fails: dict[str, int] = {}  # volume_name -> fail_count
        self._port_conflicts: dict[str, int] = {}  # port -> conflict_count

    def _hash_input(self, input_str: str | dict) -> str:
        """Create simple hash of input for comparison."""
        if isinstance(input_str, dict):
            items = sorted(input_str.items())
            return str(hash(tuple(items)))
        return str(hash(input_str))

    def _parse_cli_input(self, input_str: str | dict) -> tuple[str, str]:
        """Parse docker_cli input. Returns (command, args)."""
        if isinstance(input_str, dict):
            return input_str.get("command", ""), input_str.get("args", "") or ""
        if isinstance(input_str, str):
            try:
                parsed = json.loads(input_str)
                if isinstance(parsed, dict):
                    return parsed.get("command", ""), parsed.get("args", "") or ""
            except (json.JSONDecodeError, ValueError):
                pass
        return "", str(input_str)

    def _parse_arg(self, args: str, *flags: str) -> str | None:
        """Extract value after a flag like --name or -p from args string."""
        parts = args.split()
        for i, part in enumerate(parts):
            if part in flags and i + 1 < len(parts):
                return parts[i + 1]
        return None

    def _extract_container_name(self, input_str: str | dict) -> str | None:
        """Extract container name from docker_cli run/start/stop/exec args."""
        command, args = self._parse_cli_input(input_str)
        if command in {"run", "start", "stop", "restart", "exec", "logs", "stats", "inspect"}:
            name = self._parse_arg(args, "--name", "-n")
            if name:
                return name
            # For start/stop/exec the first non-flag arg is the container id/name
            if command in {"start", "stop", "restart", "exec", "logs", "stats", "inspect"}:
                parts = args.split()
                for part in parts:
                    if not part.startswith("-"):
                        return part
        return None

    def _extract_resource_name(self, input_str: str | dict, resource_type: str) -> str | None:
        """Extract network or volume name from docker_cli create args."""
        command, args = self._parse_cli_input(input_str)
        # e.g. command="network create", args="my-network"
        # e.g. command="volume create", args="my-volume"
        if resource_type in command and "create" in command:
            name = self._parse_arg(args, "--name", "-n")
            if name:
                return name
            # The last positional arg is typically the name
            parts = [p for p in args.split() if not p.startswith("-")]
            if parts:
                return parts[-1]
        return None

    def _extract_port(self, input_str: str | dict) -> str | None:
        """Extract host port from docker_cli run args."""
        command, args = self._parse_cli_input(input_str)
        if command == "run":
            match = re.search(r'-p\s+(\d+):', args)
            if match:
                return match.group(1)
        return None

    def _is_container_op(self, input_str: str | dict) -> bool:
        """Return True if this is a container lifecycle operation."""
        command, _ = self._parse_cli_input(input_str)
        return command in {"run", "start", "stop", "restart"}

    def _check_docker_loops(self, tool: str, input_str: str | dict, output: str | dict) -> None:
        """Check for Docker-specific loop patterns."""
        input_hash = self._hash_input(input_str)
        output_str = str(output).lower()
        command, args = self._parse_cli_input(input_str)

        # Track command history for general identical command detection (fallback check)
        self._command_history.append((tool, input_hash))

        # 1. Container operation loop (same container start/stop/run repeatedly)
        if self._is_container_op(input_str):
            container_name = self._extract_container_name(input_str)
            if container_name:
                self._container_ops[container_name] = self._container_ops.get(container_name, 0) + 1
                if self._container_ops[container_name] > self._max_retries + 1:
                    self._trigger_replan(
                        f"Container '{container_name}' operated on {self._container_ops[container_name]} times - likely failing",
                        {"container": container_name, "command": command}
                    )

        # 2. Network create conflict (only on error)
        network_name = self._extract_resource_name(input_str, "network")
        if network_name:
            if "already exists" in output_str or "conflict" in output_str:
                self._network_create_fails[network_name] = self._network_create_fails.get(network_name, 0) + 1
                if self._network_create_fails[network_name] >= self._max_retries:
                    self._trigger_replan(
                        f"Network '{network_name}' creation failed {self._max_retries} times - already exists or conflicting",
                        {"network": network_name, "error": "already exists"}
                    )

        # 3. Volume create conflict (only on error)
        volume_name = self._extract_resource_name(input_str, "volume")
        if volume_name:
            if "already exists" in output_str or "conflict" in output_str:
                self._volume_create_fails[volume_name] = self._volume_create_fails.get(volume_name, 0) + 1
                if self._volume_create_fails[volume_name] >= self._max_retries:
                    self._trigger_replan(
                        f"Volume '{volume_name}' creation failed {self._max_retries} times - already exists or conflicting",
                        {"volume": volume_name, "error": "already exists"}
                    )

        # 4. Port conflict retry (only on error)
        port = self._extract_port(input_str)
        if port:
            if "port is already allocated" in output_str or "bind: address already in use" in output_str:
                self._port_conflicts[port] = self._port_conflicts.get(port, 0) + 1
                if self._port_conflicts[port] >= self._max_retries:
                    self._trigger_replan(
                        f"Port {port} binding failed {self._max_retries} times - already in use",
                        {"port": port, "error": "already allocated"}
                    )

        # 5. Image pull retry (pulling same image multiple times)
        if command == "pull":
            img_key = args.strip()[:100]
            self._resource_attempts[img_key] = self._resource_attempts.get(img_key, 0) + 1
            if self._resource_attempts[img_key] > self._max_retries:
                self._trigger_replan(
                    f"Image pull for '{img_key}' attempted {self._resource_attempts[img_key]} times - network or auth issue?",
                    {"image": img_key}
                )

        # 6. Fallback: Identical command retry (catch-all for non-error patterns)
        # Only fires if no specific pattern above matched
        if len(self._command_history) >= self._max_retries:
            recent = self._command_history[-self._max_retries:]
            if len(set(cmd for cmd, _ in recent)) == 1 and len(set(h for _, h in recent)) == 1:
                self._trigger_replan(
                    f"Tool '{tool}' called {self._max_retries} times with identical parameters",
                    {"tool": tool, "command": command, "args": args[:200]}
                )

    def _trigger_replan(self, reason: str, loop_info: dict[str, Any]) -> None:
        """Trigger replan by raising DockerLoopException."""
        if self._loop_detected:
            return  # Already triggered

        self._loop_detected = True

        alert_message = DOCKER_REPLAN_ALERT.format(
            loop_details=f"Pattern: {reason}\nDetails: {loop_info}"
        )

        raise DockerLoopException(alert_message, {
            "reason": reason,
            "info": loop_info,
            "trajectory": self.get_trajectory()
        })

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
        """Record tool start."""
        tool_name = serialized.get("name", "unknown")
        with self._lock:
            self.trajectory.append({
                "type": "tool_start",
                "tool": tool_name,
                "input": input_str,
                "start_time": time.time(),
                "status": "in_progress",
                "run_id": str(run_id),
            })

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Record tool end and check for loops."""
        with self._lock:
            end_time = time.time()

            # Find matching tool_start event
            tool_name = None
            input_str = None
            for event in reversed(self.trajectory):
                if (
                    event.get("type") == "tool_start"
                    and event.get("status") == "in_progress"
                    and event.get("run_id") == str(run_id)
                ):
                    tool_name = event.get("tool")
                    input_str = event.get("input")  # Capture input BEFORE changing status
                    event["output"] = output
                    event["end_time"] = end_time
                    event["latency"] = end_time - event.get("start_time", end_time)
                    event["status"] = "success"
                    break

            if tool_name and input_str:
                # Check Docker-specific loops
                self._check_docker_loops(tool_name, input_str, output)

    def on_tool_error(
        self,
        error: Exception,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Record tool error."""
        with self._lock:
            end_time = time.time()
            for event in reversed(self.trajectory):
                if (
                    event.get("type") == "tool_start"
                    and event.get("status") == "in_progress"
                    and event.get("run_id") == str(run_id)
                ):
                    event["error"] = str(error)
                    event["end_time"] = end_time
                    event["status"] = "failed"
                    event["latency"] = end_time - event.get("start_time", end_time)
                    break

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Record LLM start."""
        with self._lock:
            self.trajectory.append({
                "type": "llm_start",
                "prompts": prompts,
                "start_time": time.time(),
                "run_id": str(run_id),
            })

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Record LLM end."""
        with self._lock:
            self.trajectory.append({
                "type": "llm_end",
                "end_time": time.time(),
                "run_id": str(run_id),
            })

    def get_trajectory(self) -> list[dict[str, Any]]:
        """Return trajectory data."""
        with self._lock:
            return list(self.trajectory)

    def clear(self) -> None:
        """Clear trajectory data."""
        with self._lock:
            self.trajectory.clear()
            self._command_history.clear()
            self._resource_attempts.clear()
            self._container_ops.clear()
            self._network_create_fails.clear()
            self._volume_create_fails.clear()
            self._port_conflicts.clear()
            self._loop_detected = False
