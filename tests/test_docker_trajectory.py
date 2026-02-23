"""Unit tests for DockerTrajectoryCallback with docker_cli input format."""

import json
import uuid

import pytest

from src.multi_agent.runtime.docker_trajectory import DockerLoopException, DockerTrajectoryCallback


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_input(command: str, args: str = "", cwd: str | None = None) -> str:
    """Simulate the JSON string that LangChain passes as input_str to on_tool_end."""
    payload: dict = {"command": command, "args": args}
    if cwd:
        payload["cwd"] = cwd
    return json.dumps(payload)


def _simulate_tool_call(cb: DockerTrajectoryCallback, command: str, args: str = "", output: str = "ok") -> None:
    """Push one tool_start + tool_end through the callback."""
    run_id = str(uuid.uuid4())
    cb.on_tool_start({"name": "docker_cli"}, _make_input(command, args), run_id=run_id)
    cb.on_tool_end(output, run_id=run_id)


# ---------------------------------------------------------------------------
# _parse_cli_input
# ---------------------------------------------------------------------------

class TestParseCliInput:
    def test_json_string(self):
        cb = DockerTrajectoryCallback()
        cmd, args = cb._parse_cli_input(_make_input("run", "-d --name web nginx"))
        assert cmd == "run"
        assert "--name web" in args

    def test_dict_input(self):
        cb = DockerTrajectoryCallback()
        cmd, args = cb._parse_cli_input({"command": "ps", "args": "-a"})
        assert cmd == "ps"
        assert args == "-a"

    def test_empty_args(self):
        cb = DockerTrajectoryCallback()
        cmd, args = cb._parse_cli_input(_make_input("ps"))
        assert cmd == "ps"
        assert args == ""

    def test_non_json_string_falls_back(self):
        cb = DockerTrajectoryCallback()
        cmd, args = cb._parse_cli_input("not json")
        assert cmd == ""
        assert "not json" in args


# ---------------------------------------------------------------------------
# _extract_container_name
# ---------------------------------------------------------------------------

class TestExtractContainerName:
    def test_run_with_name_flag(self):
        cb = DockerTrajectoryCallback()
        name = cb._extract_container_name(_make_input("run", "-d --name my-nginx nginx:alpine"))
        assert name == "my-nginx"

    def test_stop_with_positional_name(self):
        cb = DockerTrajectoryCallback()
        name = cb._extract_container_name(_make_input("stop", "my-nginx"))
        assert name == "my-nginx"

    def test_start_with_container_id(self):
        cb = DockerTrajectoryCallback()
        name = cb._extract_container_name(_make_input("start", "abc123"))
        assert name == "abc123"

    def test_ps_command_returns_none(self):
        cb = DockerTrajectoryCallback()
        name = cb._extract_container_name(_make_input("ps", "-a"))
        assert name is None

    def test_short_name_flag(self):
        cb = DockerTrajectoryCallback()
        name = cb._extract_container_name(_make_input("run", "-d -n app nginx"))
        assert name == "app"


# ---------------------------------------------------------------------------
# _extract_resource_name
# ---------------------------------------------------------------------------

class TestExtractResourceName:
    def test_network_create_positional(self):
        cb = DockerTrajectoryCallback()
        name = cb._extract_resource_name(_make_input("network create", "my-net"), "network")
        assert name == "my-net"

    def test_volume_create_positional(self):
        cb = DockerTrajectoryCallback()
        name = cb._extract_resource_name(_make_input("volume create", "my-vol"), "volume")
        assert name == "my-vol"

    def test_network_create_with_driver_flag(self):
        cb = DockerTrajectoryCallback()
        name = cb._extract_resource_name(_make_input("network create", "--driver bridge ci-net"), "network")
        assert name == "ci-net"

    def test_wrong_resource_type_returns_none(self):
        cb = DockerTrajectoryCallback()
        name = cb._extract_resource_name(_make_input("network create", "my-net"), "volume")
        assert name is None

    def test_non_create_command_returns_none(self):
        cb = DockerTrajectoryCallback()
        name = cb._extract_resource_name(_make_input("network ls"), "network")
        assert name is None


# ---------------------------------------------------------------------------
# _extract_port
# ---------------------------------------------------------------------------

class TestExtractPort:
    def test_run_with_port(self):
        cb = DockerTrajectoryCallback()
        port = cb._extract_port(_make_input("run", "-d -p 8080:80 nginx"))
        assert port == "8080"

    def test_run_without_port(self):
        cb = DockerTrajectoryCallback()
        port = cb._extract_port(_make_input("run", "-d --name web nginx"))
        assert port is None

    def test_non_run_command(self):
        cb = DockerTrajectoryCallback()
        port = cb._extract_port(_make_input("ps", "-p 8080:80"))
        assert port is None


# ---------------------------------------------------------------------------
# Loop detection via simulate_tool_call
# ---------------------------------------------------------------------------

class TestLoopDetection:
    def test_identical_command_triggers_replan(self):
        cb = DockerTrajectoryCallback(max_retries=3)
        with pytest.raises(DockerLoopException, match="identical parameters"):
            for _ in range(3):  # 3 calls triggers: len >= 3, then check last 3 identical
                _simulate_tool_call(cb, "ps", "-a", output="CONTAINER ID")

    def test_different_args_no_replan(self):
        cb = DockerTrajectoryCallback(max_retries=3)
        _simulate_tool_call(cb, "ps", "-a", output="ok")
        _simulate_tool_call(cb, "ps", "", output="ok")
        _simulate_tool_call(cb, "ps", "-a -q", output="ok")
        # Should NOT raise

    def test_container_op_loop_triggers_replan(self):
        cb = DockerTrajectoryCallback(max_retries=3)
        with pytest.raises(DockerLoopException, match="my-app"):
            for _ in range(5):
                _simulate_tool_call(cb, "run", "-d --name my-app nginx", output="ok")

    def test_network_already_exists_triggers_replan(self):
        cb = DockerTrajectoryCallback(max_retries=3)
        with pytest.raises(DockerLoopException, match="ci-net"):
            for _ in range(3):
                _simulate_tool_call(
                    cb, "network create", "ci-net",
                    output="Error response from daemon: network with name ci-net already exists"
                )

    def test_volume_already_exists_triggers_replan(self):
        cb = DockerTrajectoryCallback(max_retries=3)
        with pytest.raises(DockerLoopException, match="app-data"):
            for _ in range(3):
                _simulate_tool_call(
                    cb, "volume create", "app-data",
                    output="Error: volume already exists"
                )

    def test_port_conflict_triggers_replan(self):
        cb = DockerTrajectoryCallback(max_retries=3)
        with pytest.raises(DockerLoopException, match="8080"):
            for _ in range(3):
                _simulate_tool_call(
                    cb, "run", "-d -p 8080:80 nginx",
                    output="Error: port is already allocated"
                )

    def test_image_pull_retry_triggers_replan(self):
        cb = DockerTrajectoryCallback(max_retries=3)
        with pytest.raises(DockerLoopException, match="nginx:alpine"):
            for _ in range(4):
                _simulate_tool_call(cb, "pull", "nginx:alpine", output="Error: timeout")

    def test_network_success_no_replan(self):
        cb = DockerTrajectoryCallback(max_retries=3)
        # Run 2 times (below threshold) - should NOT trigger generic identical command check
        for _ in range(2):
            _simulate_tool_call(cb, "network create", "ci-net", output="abc123def456")
        # No exception — output doesn't contain "already exists" and below retry threshold

    def test_clear_resets_state(self):
        cb = DockerTrajectoryCallback(max_retries=3)
        # Trigger near-limit but don't exceed
        _simulate_tool_call(cb, "ps", "-a")
        _simulate_tool_call(cb, "ps", "-a")
        cb.clear()
        # After clear, counter resets — two more should not trigger
        _simulate_tool_call(cb, "ps", "-a")
        _simulate_tool_call(cb, "ps", "-a")
