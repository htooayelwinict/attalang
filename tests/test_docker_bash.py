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
    ]
    for command in allowed:
        docker_tools._validate_docker_command(command)


def test_validate_docker_command_rejects_unsafe_commands() -> None:
    blocked = [
        ["system", "prune"],
        ["rm", "-rf", "/"],
        ["compose", "up"],
        ["network", "create", "net"],
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

    out = json.loads(docker_tools.docker_bash.func("docker ps", args="-a", cwd="/tmp", timeout=9))

    assert out["success"] is True
    assert out["stdout"] == "ok-output"
    assert seen["args"] == ["ps", "-a"]
    assert seen["cwd"] == "/tmp"
    assert seen["timeout"] == 9


def test_docker_bash_wraps_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        docker_tools,
        "_run_safe_docker_cli",
        lambda args, cwd=None, timeout=30: (1, "", "bad command"),
    )

    out = json.loads(docker_tools.docker_bash.func("ps"))

    assert out["success"] is False
    assert "bad command" in out["error"]


def test_list_containers_returns_lean_output(monkeypatch: pytest.MonkeyPatch) -> None:
    cli = "CONTAINER ID   IMAGE\nabc123         nginx:latest\n"
    monkeypatch.setattr(docker_tools, "_run_safe_docker_cli", lambda args, cwd=None: (0, cli, ""))

    out = json.loads(docker_tools.list_containers.func(all_containers=True))

    assert out["success"] is True
    assert out["output"] == cli


def test_list_images_returns_lean_output(monkeypatch: pytest.MonkeyPatch) -> None:
    cli = "REPOSITORY   TAG   IMAGE ID\nnginx        latest abc123\n"
    monkeypatch.setattr(docker_tools, "_run_safe_docker_cli", lambda args, cwd=None: (0, cli, ""))

    out = json.loads(docker_tools.list_images.func())

    assert out["success"] is True
    assert out["output"] == cli


def test_list_networks_returns_lean_output(monkeypatch: pytest.MonkeyPatch) -> None:
    cli = "NETWORK ID   NAME     DRIVER\n123456       bridge   bridge\n"
    monkeypatch.setattr(docker_tools, "_run_safe_docker_cli", lambda args, cwd=None: (0, cli, ""))

    out = json.loads(docker_tools.list_networks.func())

    assert out["success"] is True
    assert out["output"] == cli


def test_list_volumes_returns_lean_output(monkeypatch: pytest.MonkeyPatch) -> None:
    cli = "DRIVER    VOLUME NAME\nlocal     app-data\n"
    monkeypatch.setattr(docker_tools, "_run_safe_docker_cli", lambda args, cwd=None: (0, cli, ""))

    out = json.loads(docker_tools.list_volumes.func())

    assert out["success"] is True
    assert out["output"] == cli


def test_system_and_version_return_lean_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(args: list[str], cwd: str | None = None):
        if args[0] == "info":
            payload = {"Containers": 4, "Images": 12, "ServerVersion": "29.2.1"}
            return 0, json.dumps(payload), ""
        if args[0] == "version":
            payload = {"Client": {"Version": "29.2.1"}, "Server": {"Version": "29.2.1"}}
            return 0, json.dumps(payload), ""
        raise AssertionError(f"Unexpected args: {args}")

    monkeypatch.setattr(docker_tools, "_run_safe_docker_cli", fake_run)

    info_out = json.loads(docker_tools.docker_system_info.func())
    version_out = json.loads(docker_tools.docker_version.func())

    assert info_out["success"] is True
    assert '"Containers": 4' in info_out["output"]
    assert version_out["success"] is True
    assert '"Version": "29.2.1"' in version_out["output"]


def test_all_docker_tools_reduced_and_includes_bash() -> None:
    names = [tool.name for tool in docker_tools.ALL_DOCKER_TOOLS]

    assert "docker_bash" in names
    assert "list_containers" not in names
    assert "list_images" not in names
    assert len(names) <= 20


def test_hitl_constants_unchanged() -> None:
    assert DANGEROUS_TOOLS == ("remove_image", "prune_images")
    assert AUTO_REJECT_TOOLS == ("remove_volume", "prune_volumes", "docker_system_prune")
