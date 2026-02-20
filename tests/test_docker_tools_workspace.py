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
