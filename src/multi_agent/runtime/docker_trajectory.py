"""Docker-specific trajectory callback for loop detection and replan.

Detects Docker agent loops and triggers replan instead of hard abort.
"""

import threading
import time
from typing import Any, Optional

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
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
    - Identical command retries (same docker_bash command)
    """

    def __init__(self, max_retries: int = 3) -> None:
        """Initialize the Docker trajectory callback.

        Args:
            max_retries: Max identical calls before triggering replan (default: 3)
        """
        self.trajectory: list[dict[str, Any]] = []
        self._lock = threading.Lock()
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
            # Sort keys for consistent hashing
            items = sorted(input_str.items())
            return str(hash(tuple(items)))
        return str(hash(input_str))

    def _extract_container_name(self, tool: str, input_str: str | dict) -> str | None:
        """Extract container name from tool call."""
        if "run_container" in tool or "start" in tool or "stop" in tool:
            if isinstance(input_str, dict):
                return input_str.get("name")
            if isinstance(input_str, str):
                # Parse CLI args for -n or --name
                if "-n " in input_str or "--name " in input_str:
                    parts = input_str.split()
                    for i, part in enumerate(parts):
                        if part in ["-n", "--name"] and i + 1 < len(parts):
                            return parts[i + 1]
        return None

    def _extract_resource_name(self, tool: str, input_str: str | dict, resource_type: str) -> str | None:
        """Extract resource name (network/volume) from tool call."""
        if resource_type in tool or "create" in tool:
            if isinstance(input_str, dict):
                return input_str.get("name")
            if isinstance(input_str, str):
                # Parse CLI for resource name
                parts = input_str.split()
                for i, part in enumerate(parts):
                    if part in ["-n", "--name"] and i + 1 < len(parts):
                        return parts[i + 1]
                    # Last arg might be the name
                    if i == len(parts) - 1 and not part.startswith("-"):
                        return part
        return None

    def _extract_port(self, input_str: str | dict) -> str | None:
        """Extract port number from tool call."""
        if isinstance(input_str, dict):
            ports = input_str.get("ports")
            if ports:
                return str(ports)
        if isinstance(input_str, str):
            # Look for port patterns like "-p 8080:80" or "8080:80"
            import re
            match = re.search(r'-p\s+(\d+):', input_str)
            if match:
                return match.group(1)
        return None

    def _check_docker_loops(self, tool: str, input_str: str | dict, output: str | dict) -> None:
        """Check for Docker-specific loop patterns."""
        input_hash = self._hash_input(input_str)

        # 1. Identical command retry
        self._command_history.append((tool, input_hash))
        if len(self._command_history) >= self._max_retries:
            recent = self._command_history[-self._max_retries:]
            if len(set(cmd for cmd, _ in recent)) == 1 and len(set(h for _, h in recent)) == 1:
                self._trigger_replan(
                    f"Tool '{tool}' called {self._max_retries} times with identical parameters",
                    {"tool": tool, "input": str(input_str)[:200]}
                )

        # 2. Container operation loop (start/stop same container repeatedly)
        container_name = self._extract_container_name(tool, input_str)
        if container_name and ("start" in tool or "stop" in tool or "run" in tool):
            self._container_ops[container_name] = self._container_ops.get(container_name, 0) + 1
            if self._container_ops[container_name] > self._max_retries + 1:
                self._trigger_replan(
                    f"Container '{container_name}' operated on {self._container_ops[container_name]} times - likely failing",
                    {"container": container_name, "operation": tool}
                )

        # 3. Network create conflict
        network_name = self._extract_resource_name(tool, input_str, "network")
        if network_name and "create" in tool:
            # Check if output indicates "already exists"
            output_str = str(output).lower()
            if "already exists" in output_str or "conflict" in output_str:
                self._network_create_fails[network_name] = self._network_create_fails.get(network_name, 0) + 1
                if self._network_create_fails[network_name] >= self._max_retries:
                    self._trigger_replan(
                        f"Network '{network_name}' creation failed {self._max_retries} times - already exists or conflicting",
                        {"network": network_name, "error": "already exists"}
                    )

        # 4. Volume create conflict
        volume_name = self._extract_resource_name(tool, input_str, "volume")
        if volume_name and "create" in tool:
            output_str = str(output).lower()
            if "already exists" in output_str or "conflict" in output_str:
                self._volume_create_fails[volume_name] = self._volume_create_fails.get(volume_name, 0) + 1
                if self._volume_create_fails[volume_name] >= self._max_retries:
                    self._trigger_replan(
                        f"Volume '{volume_name}' creation failed {self._max_retries} times - already exists or conflicting",
                        {"volume": volume_name, "error": "already exists"}
                    )

        # 5. Port conflict retry
        port = self._extract_port(input_str)
        if port:
            output_str = str(output).lower()
            if "port is already allocated" in output_str or "bind: address already in use" in output_str:
                self._port_conflicts[port] = self._port_conflicts.get(port, 0) + 1
                if self._port_conflicts[port] >= self._max_retries:
                    self._trigger_replan(
                        f"Port {port} binding failed {self._max_retries} times - already in use",
                        {"port": port, "error": "already allocated"}
                    )

        # 6. Image pull retry (pulling same image multiple times)
        if "pull" in tool:
            img_name = str(input_str)[:100]  # First 100 chars usually has image name
            self._resource_attempts[img_name] = self._resource_attempts.get(img_name, 0) + 1
            if self._resource_attempts[img_name] > self._max_retries:
                self._trigger_replan(
                    f"Image pull for '{img_name}' attempted {self._resource_attempts[img_name]} times - network or auth issue?",
                    {"image": img_name}
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
            for event in reversed(self.trajectory):
                if (
                    event.get("type") == "tool_start"
                    and event.get("status") == "in_progress"
                    and event.get("run_id") == str(run_id)
                ):
                    tool_name = event.get("tool")
                    event["output"] = output
                    event["end_time"] = end_time
                    event["latency"] = end_time - event.get("start_time", end_time)
                    event["status"] = "success"
                    break

            if tool_name:
                # Check Docker-specific loops
                input_str = next(
                    (e.get("input") for e in reversed(self.trajectory)
                     if e.get("run_id") == str(run_id) and e.get("type") == "tool_start"),
                    ""
                )
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
