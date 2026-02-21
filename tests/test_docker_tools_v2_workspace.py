import json
from pathlib import Path

import pytest

from src.multi_agent_v2.tools import docker_tools_v2


def test_v2_resolve_workspace_absolute_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(docker_tools_v2.WORKSPACE_ENV_VAR, str(tmp_path))

    resolved = docker_tools_v2._resolve_workspace_path("/Dockerfile")

    assert resolved == tmp_path / "Dockerfile"


def test_v2_resolve_workspace_rejects_escape(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(docker_tools_v2.WORKSPACE_ENV_VAR, str(tmp_path))

    with pytest.raises(ValueError):
        docker_tools_v2._resolve_workspace_path("../../outside")


def test_v2_parse_services_json() -> None:
    services = docker_tools_v2._parse_services('["api", "db"]')
    assert services == ["api", "db"]


def test_v2_parse_services_csv() -> None:
    services = docker_tools_v2._parse_services("api, db ,worker")
    assert services == ["api", "db", "worker"]


def test_v2_truncate_text_keeps_head_and_tail() -> None:
    value = ("a" * 40) + ("b" * 40)

    out = docker_tools_v2._truncate_text(value, max_chars=20)

    assert "... [TRUNCATED 60 chars of logs] ..." in out
    assert out.startswith("a" * 10)
    assert out.endswith("b" * 10)


def test_v2_json_truncates_large_string_values() -> None:
    payload = {"success": True, "logs": "x" * 3000}

    out = docker_tools_v2._json(payload)

    assert '"success": true' in out
    assert "[TRUNCATED" in out


def test_v2_truncate_data_limits_list_items() -> None:
    payload = {"items": list(range(6))}

    out = docker_tools_v2._truncate_data(payload, max_list_items=3)

    assert out["items"] == [0, 1, 2, {"_truncated_items": 3}]


def test_v2_json_enforces_global_response_budget() -> None:
    payload = {"success": True, "items": [{"line": "x" * 1200} for _ in range(120)]}

    out = docker_tools_v2._json(payload)

    assert "[TRUNCATED" in out


def test_v2_run_compose_returns_raw_output(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyResult:
        returncode = 0
        stdout = "a" * 5000
        stderr = "b" * 5000

    monkeypatch.setattr(docker_tools_v2, "_compose_prefix", lambda: ["docker", "compose"])
    monkeypatch.setattr(docker_tools_v2.subprocess, "run", lambda *args, **kwargs: DummyResult())

    code, stdout, stderr = docker_tools_v2._run_compose(args=["ps"], cwd="/tmp")

    assert code == 0
    assert len(stdout) == 5000
    assert len(stderr) == 5000


def test_v2_compose_ps_parses_before_output_truncation(monkeypatch: pytest.MonkeyPatch) -> None:
    long_json = json.dumps([{"Name": "api", "Detail": "x" * 2500}])

    monkeypatch.setattr(
        docker_tools_v2,
        "_compose_file_and_cwd",
        lambda file_path, cwd: (Path("/tmp/docker-compose.yml"), Path("/tmp")),
    )
    monkeypatch.setattr(docker_tools_v2, "_run_compose", lambda args, cwd=None: (0, long_json, ""))

    out = docker_tools_v2.compose_ps(file_path="/docker-compose.yml", format_json=True)
    parsed_out = json.loads(out)

    assert parsed_out["success"] is True
    assert parsed_out["parsed"] is not None
    assert parsed_out["parsed"][0]["Name"] == "api"


def test_register_tools_on_agent_supports_both_tool_signatures() -> None:
    called: list[str] = []

    class AgentOne:
        def tool(self, fn=None):
            if fn is None:
                raise TypeError("expected fn")
            called.append(f"direct:{fn.__name__}")
            return fn

    class AgentTwo:
        def tool(self, fn=None):
            if fn is not None:
                raise TypeError("use decorator")

            def decorator(real_fn):
                called.append(f"decorator:{real_fn.__name__}")
                return real_fn

            return decorator

    docker_tools_v2.register_tools_on_agent(AgentOne(), tools=[docker_tools_v2.list_containers])
    docker_tools_v2.register_tools_on_agent(AgentTwo(), tools=[docker_tools_v2.list_images])

    assert called == ["direct:list_containers", "decorator:list_images"]
