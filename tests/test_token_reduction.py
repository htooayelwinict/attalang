import json

import pytest

from src.multi_agent.tools import docker_tools


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _assert_reduction_at_least_70_percent(legacy_text: str, modern_text: str) -> None:
    legacy_tokens = _approx_tokens(legacy_text)
    modern_tokens = _approx_tokens(modern_text)
    reduction = 1.0 - (modern_tokens / legacy_tokens)
    assert reduction >= 0.70, (
        f"Expected >=70% reduction, got {reduction * 100:.2f}% "
        f"(legacy={legacy_tokens}, modern={modern_tokens})"
    )


def test_list_containers_token_reduction(monkeypatch: pytest.MonkeyPatch) -> None:
    cli_lines = []
    for idx in range(2):
        cli_lines.append(
            json.dumps(
                {
                    "ID": f"{idx:02d}" * 8,
                    "Names": f"service-{idx}",
                    "Status": "Up 1 hour",
                    "Image": "nginx:latest",
                    "Ports": f"0.0.0.0:{8000 + idx}->80/tcp",
                    "CreatedAt": "2026-02-22 10:00:00 +0000 UTC",
                }
            )
        )
    cli_output = "\n".join(cli_lines)
    monkeypatch.setattr(
        docker_tools,
        "_run_safe_docker_cli",
        lambda args, cwd=None: (0, cli_output, ""),
    )

    modern_text = docker_tools.list_containers.func(all_containers=True)

    legacy_text = docker_tools._json(
        {
            "success": True,
            "count": 2,
            "containers": [
                {
                    "id": f"{idx:02d}" * 8,
                    "name": f"service-{idx}",
                    "status": "running",
                    "image": "nginx:latest",
                    "ports": {
                        "80/tcp": [
                            {"HostIp": "0.0.0.0", "HostPort": str(8000 + idx)},
                            {"HostIp": "::", "HostPort": str(8000 + idx)},
                        ]
                    },
                    "created": "2026-02-22T10:00:00Z",
                    "network_settings": {
                        "bridge": {
                            "ip_address": f"172.17.0.{idx + 2}",
                            "gateway": "172.17.0.1",
                            "mac": "02:42:ac:11:00:02",
                        }
                    },
                    "labels": {f"label-{n}": "x" * 60 for n in range(10)},
                }
                for idx in range(2)
            ],
        }
    )

    _assert_reduction_at_least_70_percent(legacy_text, modern_text)


def test_get_container_logs_token_reduction(monkeypatch: pytest.MonkeyPatch) -> None:
    logs_text = "\n".join(f"log line {i}" for i in range(25))

    def fake_run(args: list[str], cwd: str | None = None):
        if args[0] == "logs":
            return 0, logs_text, ""
        if args[0] == "inspect":
            payload = [{"Id": "0123456789abcdef", "Name": "/web", "State": {"Status": "running"}}]
            return 0, json.dumps(payload), ""
        raise AssertionError(f"Unexpected args: {args}")

    monkeypatch.setattr(docker_tools, "_run_safe_docker_cli", fake_run)

    modern_text = docker_tools.get_container_logs.func(container_id="web", tail=25)

    legacy_text = docker_tools._json(
        {
            "success": True,
            "container_id": "0123456789ab",
            "container_name": "web",
            "logs": logs_text,
            "log_meta": [{"line": i, "ts": f"2026-02-22T10:{i:02d}:00Z"} for i in range(25)],
            "container_snapshot": {
                "mounts": [{"src": f"/var/lib/{i}", "dst": f"/data/{i}"} for i in range(30)],
                "env": [f"KEY_{i}={'x' * 40}" for i in range(30)],
            },
        }
    )

    _assert_reduction_at_least_70_percent(legacy_text, modern_text)


def test_start_container_token_reduction(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(args: list[str], cwd: str | None = None):
        if args[0] == "start":
            return 0, "web\n", ""
        if args[0] == "inspect":
            payload = [{"Id": "0123456789abcdef", "Name": "/web", "State": {"Status": "running"}}]
            return 0, json.dumps(payload), ""
        raise AssertionError(f"Unexpected args: {args}")

    monkeypatch.setattr(docker_tools, "_run_safe_docker_cli", fake_run)

    modern_text = docker_tools.start_container.func(container_id="web")

    legacy_text = docker_tools._json(
        {
            "success": True,
            "container_id": "0123456789ab",
            "container_name": "web",
            "status": "running",
            "host_config": {
                "port_bindings": {f"{p}/tcp": [{"HostPort": str(8000 + p)}] for p in range(40)},
                "restart_policy": {"Name": "always"},
            },
            "network": {
                "ports": {
                    f"{p}/tcp": [{"HostIp": "0.0.0.0", "HostPort": str(8000 + p)}]
                    for p in range(40)
                }
            },
        }
    )

    _assert_reduction_at_least_70_percent(legacy_text, modern_text)
