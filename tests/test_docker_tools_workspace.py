import json
from pathlib import Path

import pytest

from src.multi_agent.tools import docker_tools


def test_resolve_workspace_absolute_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(docker_tools.WORKSPACE_ENV_VAR, str(tmp_path))

    resolved = docker_tools._resolve_workspace_path("/Dockerfile")

    assert resolved == tmp_path / "Dockerfile"


def test_resolve_workspace_rejects_escape(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(docker_tools.WORKSPACE_ENV_VAR, str(tmp_path))

    with pytest.raises(ValueError):
        docker_tools._resolve_workspace_path("../../outside")


def test_parse_services_json() -> None:
    services = docker_tools._parse_services('["api", "db"]')
    assert services == ["api", "db"]


def test_parse_services_csv() -> None:
    services = docker_tools._parse_services("api, db ,worker")
    assert services == ["api", "db", "worker"]


def test_truncate_text_keeps_head_and_tail() -> None:
    value = ("a" * 40) + ("b" * 40)

    out = docker_tools._truncate_text(value, max_chars=20)

    assert "... [TRUNCATED 60 chars of logs] ..." in out
    assert out.startswith("a" * 10)
    assert out.endswith("b" * 10)


def test_json_truncates_large_string_values() -> None:
    payload = {"success": True, "logs": "x" * 3000}

    out = docker_tools._json(payload)

    assert '"success": true' in out
    assert "[TRUNCATED" in out


def test_truncate_data_limits_list_items() -> None:
    payload = {"items": list(range(6))}

    out = docker_tools._truncate_data(payload, max_list_items=3)

    assert out["items"] == [0, 1, 2, {"_truncated_items": 3}]


def test_json_enforces_global_response_budget() -> None:
    payload = {"success": True, "items": [{"line": "x" * 1200} for _ in range(120)]}

    out = docker_tools._json(payload)

    assert "[TRUNCATED" in out


def test_run_compose_returns_raw_output(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyResult:
        returncode = 0
        stdout = "a" * 5000
        stderr = "b" * 5000

    monkeypatch.setattr(docker_tools, "_compose_prefix", lambda: ["docker", "compose"])
    monkeypatch.setattr(docker_tools.subprocess, "run", lambda *args, **kwargs: DummyResult())

    code, stdout, stderr = docker_tools._run_compose(args=["ps"], cwd="/tmp")

    assert code == 0
    assert len(stdout) == 5000
    assert len(stderr) == 5000


def test_compose_ps_parses_before_output_truncation(monkeypatch: pytest.MonkeyPatch) -> None:
    long_json = json.dumps([{"Name": "api", "Detail": "x" * 2500}])

    monkeypatch.setattr(
        docker_tools,
        "_compose_file_and_cwd",
        lambda file_path, cwd: (Path("/tmp/docker-compose.yml"), Path("/tmp")),
    )
    monkeypatch.setattr(docker_tools, "_run_compose", lambda args, cwd=None: (0, long_json, ""))

    out = docker_tools.compose_ps.func(file_path="/docker-compose.yml", format_json=True)
    parsed_out = json.loads(out)

    assert parsed_out["success"] is True
    assert parsed_out["parsed"] is not None
    assert parsed_out["parsed"][0]["Name"] == "api"
