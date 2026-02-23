import json
import os
import shlex
import shutil
import subprocess
import sys
from typing import Any

from langchain.tools import tool
from pydantic import BaseModel, Field

MAX_TOOL_STRING_CHARS = int(os.getenv("DOCKER_TOOL_MAX_STRING_CHARS", "1200"))
MAX_TOOL_LIST_ITEMS = int(os.getenv("DOCKER_TOOL_MAX_LIST_ITEMS", "120"))
MAX_TOOL_DICT_ITEMS = int(os.getenv("DOCKER_TOOL_MAX_DICT_ITEMS", "200"))
MAX_TOOL_RESPONSE_CHARS = int(os.getenv("DOCKER_TOOL_MAX_RESPONSE_CHARS", "4000"))
DOCKER_CLI_TIMEOUT_SECONDS = int(os.getenv("DOCKER_CLI_TIMEOUT_SECONDS", "30"))

SAFE_DOCKER_COMMANDS: tuple[str, ...] = (
    "ps",
    "images",
    "logs",
    "stats",
    "inspect",
    "start",
    "stop",
    "restart",
    "network ls",
    "network inspect",
    "volume ls",
    "volume inspect",
    "info",
    "version",
    "compose ps",
    "compose logs",
    "run",
    "pull",
    "build",
    "tag",
    "network create",
    "volume create",
    "network connect",
    "network disconnect",
    "exec",
    "compose up",
    "compose down",
)


def _truncate_text(value: str, max_chars: int = MAX_TOOL_STRING_CHARS) -> str:
    if len(value) <= max_chars:
        return value
    half = max_chars // 2
    omitted = len(value) - max_chars
    suffix = value[-half:] if half > 0 else ""
    return f"{value[:half]}\n... [TRUNCATED {omitted} chars of logs] ...\n{suffix}"


def _truncate_data(
    value: Any,
    max_chars: int = MAX_TOOL_STRING_CHARS,
    max_list_items: int = MAX_TOOL_LIST_ITEMS,
    max_dict_items: int = MAX_TOOL_DICT_ITEMS,
) -> Any:
    if isinstance(value, str):
        return _truncate_text(value, max_chars=max_chars)
    if isinstance(value, bytes):
        return _truncate_text(_as_text(value), max_chars=max_chars)
    if isinstance(value, (list, tuple, set, frozenset)):
        val_list = list(value) if isinstance(value, (set, frozenset)) else value
        items = [
            _truncate_data(
                item,
                max_chars=max_chars,
                max_list_items=max_list_items,
                max_dict_items=max_dict_items,
            )
            for item in val_list[:max_list_items]
        ]
        if len(val_list) > max_list_items:
            items.append({"_truncated_items": len(val_list) - max_list_items})

        if isinstance(value, tuple):
            return tuple(items)
        return items
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for idx, (key, item) in enumerate(value.items()):
            if idx >= max_dict_items:
                out["_truncated_keys"] = len(value) - max_dict_items
                break
            out[key] = _truncate_data(
                item,
                max_chars=max_chars,
                max_list_items=max_list_items,
                max_dict_items=max_dict_items,
            )
        return out
    return value


def _json(data: dict[str, Any]) -> str:
    serialized = json.dumps(_truncate_data(data), indent=2, default=str)
    return _truncate_text(serialized, max_chars=MAX_TOOL_RESPONSE_CHARS)


def _ok(**data: Any) -> str:
    return _json({"success": True, **data})


def _error(message: str, **data: Any) -> str:
    return _json({"success": False, "error": message, **data})


def _as_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _docker_module() -> Any:
    try:
        import docker  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Docker SDK for Python is not installed. Add dependency 'docker'."
        ) from exc
    return docker


def _docker_client() -> Any:
    docker = _docker_module()
    base_url = (
        "npipe:////./pipe/docker_engine"
        if sys.platform == "win32"
        else "unix:///var/run/docker.sock"
    )

    try:
        client = docker.DockerClient(base_url=base_url, version="auto")
        client.ping()
        return client
    except Exception:
        try:
            client = docker.from_env()
            client.ping()
            return client
        except Exception as exc:
            raise RuntimeError(f"Unable to connect to Docker daemon: {exc}") from exc


def _docker_binary() -> str:
    docker_binary = shutil.which("docker")
    if docker_binary:
        return docker_binary
    raise RuntimeError("Docker CLI is not available. Install Docker to use this toolset.")


TRUNCATE_OUTPUT_COMMANDS: frozenset[str] = frozenset({
    "logs", "inspect", "stats", "ps", "images", "compose logs", "compose ps"
})


def _extract_command_key(args: list[str]) -> str:
    if not args:
        raise ValueError("Docker command is required")

    first = args[0]
    if first == "compose":
        idx = 1
        while idx < len(args):
            token = args[idx]
            if token in {"-f", "--file", "-p", "--project-name", "--profile"}:
                idx += 2
                continue
            if token.startswith("-"):
                idx += 1
                continue
            return f"compose {token}"
        raise ValueError("Docker compose subcommand is required")

    if first in {"network", "volume"}:
        if len(args) < 2:
            raise ValueError(f"'docker {first}' subcommand is required")
        return f"{first} {args[1]}"

    return first


def _validate_docker_command(args: list[str]) -> None:
    if not args:
        raise ValueError("Docker command is required")

    for token in args:
        if any(marker in token for marker in (";", "&&", "||", "|", "`", "$(")):
            raise ValueError("Shell control operators are not allowed")

    key = _extract_command_key(args)
    if key not in SAFE_DOCKER_COMMANDS:
        raise ValueError(f"Command not allowed: {key}")


def _run_docker_cli(
    args: list[str],
    cwd: str | None = None,
    timeout: int = DOCKER_CLI_TIMEOUT_SECONDS,
) -> tuple[int, str, str]:
    docker_binary = _docker_binary()
    try:
        result = subprocess.run(
            [docker_binary, *args],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as exc:
        stdout = _as_text(exc.stdout) if exc.stdout else ""
        return 124, stdout, f"Docker command timed out after {timeout}s"


def _run_safe_docker_cli(
    args: list[str],
    cwd: str | None = None,
    timeout: int = DOCKER_CLI_TIMEOUT_SECONDS,
) -> tuple[int, str, str]:
    _validate_docker_command(args)
    return _run_docker_cli(args=args, cwd=cwd, timeout=timeout)


class DockerBashInput(BaseModel):
    command: str = Field(description="Docker subcommand, for example: ps, run, build, compose up")
    args: str | None = Field(default=None, description="Optional arguments for the command")
    cwd: str | None = Field(
        default=None,
        description="Optional working directory (for build, compose commands)",
    )
    timeout: int = Field(
        default=DOCKER_CLI_TIMEOUT_SECONDS, description="Command timeout in seconds"
    )


@tool(args_schema=DockerBashInput)
def docker_cli(
    command: str,
    args: str | None = None,
    cwd: str | None = None,
    timeout: int = DOCKER_CLI_TIMEOUT_SECONDS,
) -> str:
    """Execute whitelisted Docker CLI commands. Returns raw stdout on success, error string on failure.

    Supported commands: ps, images, logs, stats, inspect, start, stop, restart, run, pull, build, tag,
    network ls/create/inspect/connect/disconnect, volume ls/create/inspect, info, version,
    compose ps/logs/up/down.

    Examples:
    - docker_cli("ps", "-a")
    - docker_cli("run", "-d -p 8080:80 nginx:latest")
    - docker_cli("build", "-t myapp .", cwd="/workspace")
    - docker_cli("compose up", "-d --build", cwd="/workspace")
    """
    try:
        command_parts = shlex.split(command)
        arg_parts = shlex.split(args) if args else []
        full_args = command_parts + arg_parts
        if full_args and full_args[0] == "docker":
            full_args = full_args[1:]

        if not full_args:
            return "Error: Docker command is required"

        code, stdout, stderr = _run_safe_docker_cli(full_args, cwd=cwd, timeout=timeout)
        if code == 0:
            try:
                cmd_key = _extract_command_key(full_args)
            except ValueError:
                cmd_key = ""
            if cmd_key in TRUNCATE_OUTPUT_COMMANDS:
                return _truncate_text(stdout, max_chars=MAX_TOOL_RESPONSE_CHARS)
            return stdout
        return f"Error (exit {code}): {stderr.strip() or 'Command failed'}"
    except Exception as exc:
        return f"Error: {str(exc)}"

# HITL (Human-in-the-Loop) tools - kept as SDK tools for safety
AGENT_DANGEROUS_SDK_TOOLS: list[Any] = []

@tool
def remove_container(container_id: str, force: bool = False, remove_volumes: bool = False) -> str:
    """Remove a container (HITL - requires human confirmation)."""
    try:
        client = _docker_client()
        container = client.containers.get(container_id)
        container.remove(force=force, v=remove_volumes)
        return _ok(container_id=container.short_id, container_name=container.name)
    except Exception as exc:
        return _error(str(exc))


@tool
def remove_image(image: str, force: bool = False, noprune: bool = False) -> str:
    """Remove an image (HITL - requires human confirmation)."""
    try:
        client = _docker_client()
        result = client.images.remove(image=image, force=force, noprune=noprune)
        return _ok(removed=image, details=result)
    except Exception as exc:
        return _error(str(exc))


@tool
def prune_images(dangling_only: bool = True) -> str:
    """Prune unused images (HITL - requires human confirmation)."""
    try:
        client = _docker_client()
        filters = {"dangling": str(dangling_only).lower()}
        result = client.images.prune(filters=filters)
        return _ok(result=result)
    except Exception as exc:
        return _error(str(exc))


@tool
def remove_network(network_id: str) -> str:
    """Remove a network (HITL - requires human confirmation)."""
    try:
        client = _docker_client()
        network = client.networks.get(network_id)
        network_name = network.name
        network.remove()
        return _ok(network_id=network.short_id, network_name=network_name)
    except Exception as exc:
        return _error(str(exc))


@tool
def remove_volume(name: str, force: bool = False) -> str:
    """Remove a named volume (HITL - requires human confirmation)."""
    try:
        client = _docker_client()
        volume = client.volumes.get(name)
        volume.remove(force=force)
        return _ok(volume_name=name)
    except Exception as exc:
        return _error(str(exc))


@tool
def prune_volumes() -> str:
    """Prune unused volumes (HITL - requires human confirmation)."""
    try:
        client = _docker_client()
        result = client.volumes.prune()
        return _ok(result=result)
    except Exception as exc:
        return _error(str(exc))


@tool
def docker_system_prune(
    all_resources: bool = False,
    volumes: bool = False,
    build_cache: bool = False,
) -> str:
    """Prune stopped containers, networks, images, and optional volumes/cache (HITL - requires human confirmation)."""
    try:
        client = _docker_client()

        container_result = client.containers.prune()
        network_result = client.networks.prune()
        image_filters = {"dangling": "false"} if all_resources else {"dangling": "true"}
        image_result = client.images.prune(filters=image_filters)
        volume_result: dict[str, Any] | None = client.volumes.prune() if volumes else None

        build_cache_result: dict[str, Any] | None = None
        if build_cache and hasattr(client.api, "prune_builds"):
            build_cache_result = client.api.prune_builds()

        return _ok(
            containers=container_result,
            networks=network_result,
            images=image_result,
            volumes=volume_result,
            build_cache=build_cache_result,
        )
    except Exception as exc:
        return _error(str(exc))


# Update the list after all tool functions are defined
AGENT_DANGEROUS_SDK_TOOLS.extend([
    remove_container,
    remove_image,
    prune_images,
    remove_network,
    remove_volume,
    prune_volumes,
    docker_system_prune,
])

# Tool lists for backward compatibility
ALL_DOCKER_TOOLS = [docker_cli] + AGENT_DANGEROUS_SDK_TOOLS

__all__ = [
    "docker_cli",
    "remove_container",
    "remove_image",
    "prune_images",
    "remove_network",
    "remove_volume",
    "prune_volumes",
    "docker_system_prune",
    "ALL_DOCKER_TOOLS",
    "AGENT_DANGEROUS_SDK_TOOLS",
    "SAFE_DOCKER_COMMANDS",
]
