import json
from typing import Callable

from src.multi_agent.tools import docker_tools


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _first_container_name() -> str | None:
    raw = docker_tools.list_containers.func(all_containers=True)
    payload = json.loads(raw)
    containers = payload.get("containers", [])
    if not containers:
        return None
    first = containers[0]
    name = first.get("name")
    return str(name) if name else None


def main() -> None:
    baselines = {
        "list_containers": 250,
        "list_images": 220,
        "docker_system_info": 230,
        "docker_version": 180,
        "get_container_logs": 180,
    }

    operations: dict[str, Callable[[], str]] = {
        "list_containers": lambda: docker_tools.list_containers.func(all_containers=True),
        "list_images": lambda: docker_tools.list_images.func(),
        "docker_system_info": lambda: docker_tools.docker_system_info.func(),
        "docker_version": lambda: docker_tools.docker_version.func(),
    }

    container_name = _first_container_name()
    if container_name:
        operations["get_container_logs"] = lambda: docker_tools.get_container_logs.func(
            container_id=container_name,
            tail=50,
        )

    print("operation,chars,est_tokens,baseline_tokens,savings_percent,status")
    for name, fn in operations.items():
        baseline = baselines.get(name, 0)
        try:
            output = fn()
            tokens = _approx_tokens(output)
            chars = len(output)
            if baseline > 0:
                savings = (1.0 - (tokens / baseline)) * 100.0
            else:
                savings = 0.0
            print(f"{name},{chars},{tokens},{baseline},{savings:.2f},ok")
        except Exception as exc:
            print(f"{name},0,0,{baseline},0.00,error:{exc}")


if __name__ == "__main__":
    main()
