import json
import subprocess

import pytest

from src.multi_agent.agents.docker_agent import AUTO_REJECT_TOOLS, DANGEROUS_TOOLS
from src.multi_agent.tools import docker_tools


def test_validate_docker_command_allows_safe_commands() -> None:
    allowed = [
        ["ps"],
        ["images"],
        ["logs", "nginx"],
        ["stats", "--no-stream", "nginx"],
        ["inspect", "--type", "container", "nginx"],
        ["start", "nginx"],
        ["stop", "nginx"],
        ["restart", "nginx"],
        ["network", "ls"],
        ["network", "inspect", "bridge"],
        ["volume", "ls"],
        ["volume", "inspect", "data"],
        ["info", "--format", "json"],
        ["version", "--format", "json"],
        ["compose", "-f", "/tmp/compose.yml", "ps"],
        ["compose", "-f", "/tmp/compose.yml", "logs"],
        # New allowed commands
        ["run", "-d", "nginx:latest"],
        ["pull", "nginx:latest"],
        ["build", "-t", "myapp", "."],
        ["tag", "myapp", "myapp:v1"],
        ["network", "create", "mynet"],
        ["volume", "create", "myvol"],
        ["network", "connect", "mynet", "nginx"],
        ["network", "disconnect", "mynet", "nginx"],
        ["exec", "nginx", "ls", "/"],
        ["compose", "up", "-d"],
        ["compose", "down"],
    ]
    for command in allowed:
        docker_tools._validate_docker_command(command)


def test_validate_docker_command_rejects_unsafe_commands() -> None:
    blocked = [
        ["system", "prune"],
        ["rm", "-rf", "/"],
        ["ls", "-la"],
        ["ps", ";", "rm", "-rf", "/"],
    ]
    for command in blocked:
        with pytest.raises(ValueError):
            docker_tools._validate_docker_command(command)


def test_extract_command_key_supports_compose_global_flags() -> None:
    key = docker_tools._extract_command_key(
        ["compose", "-f", "/tmp/docker-compose.yml", "-p", "demo", "ps"]
    )
    assert key == "compose ps"


def test_run_docker_cli_timeout_is_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(docker_tools, "_docker_binary", lambda: "docker")

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr(docker_tools.subprocess, "run", fake_run)

    code, stdout, stderr = docker_tools._run_docker_cli(["ps"], timeout=7)

    assert code == 124
    assert stdout == ""
    assert stderr == "Docker command timed out after 7s"


def test_docker_bash_wraps_success(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_run(args: list[str], cwd: str | None = None, timeout: int = 30):
        seen["args"] = args
        seen["cwd"] = cwd
        seen["timeout"] = timeout
        return 0, "ok-output", ""

    monkeypatch.setattr(docker_tools, "_run_safe_docker_cli", fake_run)

    out = docker_tools.docker_bash.func("docker ps", args="-a", cwd="/tmp", timeout=9)

    assert out == "ok-output"
    assert seen["args"] == ["ps", "-a"]
    assert seen["cwd"] == "/tmp"
    assert seen["timeout"] == 9


def test_docker_bash_wraps_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        docker_tools,
        "_run_safe_docker_cli",
        lambda args, cwd=None, timeout=30: (1, "", "bad command"),
    )

    out = docker_tools.docker_bash.func("ps")

    assert out.startswith("Error (exit 1)")
    assert "bad command" in out


def test_docker_bash_run_command(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_run(args: list[str], cwd: str | None = None, timeout: int = 30):
        seen["args"] = args
        seen["cwd"] = cwd
        seen["timeout"] = timeout
        return 0, "container-abc123", ""

    monkeypatch.setattr(docker_tools, "_run_safe_docker_cli", fake_run)

    out = docker_tools.docker_bash.func("run", args="-d -p 8080:80 nginx:latest")

    assert out == "container-abc123"
    assert seen["args"] == ["run", "-d", "-p", "8080:80", "nginx:latest"]


def test_docker_bash_exec_command(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(args: list[str], cwd: str | None = None, timeout: int = 30):
        return 0, "file1.txt\nfile2.txt\n", ""

    monkeypatch.setattr(docker_tools, "_run_safe_docker_cli", fake_run)

    out = docker_tools.docker_bash.func("exec", args="nginx ls /app")

    assert out == "file1.txt\nfile2.txt\n"


def test_docker_bash_compose_up(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_run(args: list[str], cwd: str | None = None, timeout: int = 30):
        seen["args"] = args
        seen["cwd"] = cwd
        return 0, "Container started\n", ""

    monkeypatch.setattr(docker_tools, "_run_safe_docker_cli", fake_run)

    out = docker_tools.docker_bash.func("compose up", args="-d --build", cwd="/workspace")

    assert out == "Container started\n"
    assert seen["args"] == ["compose", "up", "-d", "--build"]
    assert seen["cwd"] == "/workspace"


def test_all_docker_tools_reduced_and_includes_bash() -> None:
    names = [tool.name for tool in docker_tools.ALL_DOCKER_TOOLS]

    assert "docker_bash" in names
    # HITL tools should still be present
    assert "remove_container" in names
    assert "remove_image" in names
    assert "prune_images" in names
    assert "docker_system_prune" in names
    # Old SDK tools should be gone
    assert "list_containers" not in names
    assert "run_container" not in names
    assert len(names) <= 10  # Should be much smaller now


def test_hitl_constants_updated() -> None:
    # Updated DANGEROUS_TOOLS includes remove operations
    assert "remove_container" in DANGEROUS_TOOLS
    assert "remove_image" in DANGEROUS_TOOLS
    assert "remove_network" in DANGEROUS_TOOLS
    assert "prune_images" in DANGEROUS_TOOLS

    # AUTO_REJECT_TOOLS unchanged
    assert AUTO_REJECT_TOOLS == ("remove_volume", "prune_volumes", "docker_system_prune")


def test_safe_docker_commands_expanded() -> None:
    safe_commands = docker_tools.SAFE_DOCKER_COMMANDS
    # Original safe commands
    assert "ps" in safe_commands
    assert "images" in safe_commands
    assert "logs" in safe_commands
    # New safe commands
    assert "run" in safe_commands
    assert "pull" in safe_commands
    assert "build" in safe_commands
    assert "tag" in safe_commands
    assert "network create" in safe_commands
    assert "volume create" in safe_commands
    assert "network connect" in safe_commands
    assert "network disconnect" in safe_commands
    assert "exec" in safe_commands
    assert "compose up" in safe_commands
    assert "compose down" in safe_commands
