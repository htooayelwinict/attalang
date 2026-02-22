import json
import os
import platform
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from langchain.tools import tool
from pydantic import BaseModel, Field

WORKSPACE_ENV_VAR = "MULTI_AGENT_DOCKER_WORKSPACE"
WORKSPACE_DEFAULT = "/tmp/multi-agent-docker-workspace"
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
)


def _workspace_root() -> Path:
    root = Path(os.getenv(WORKSPACE_ENV_VAR, WORKSPACE_DEFAULT)).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve_workspace_path(path: str | None) -> Path:
    root = _workspace_root()
    if not path or path.strip() in {"", "/"}:
        return root

    raw = path.strip()
    candidate = root / raw.lstrip("/") if raw.startswith("/") else root / raw
    resolved = candidate.expanduser().resolve()

    if resolved != root and root not in resolved.parents:
        raise ValueError(f"Path must stay inside workspace root: {root}")

    return resolved


def _truncate_text(value: str, max_chars: int = MAX_TOOL_STRING_CHARS) -> str:
    if len(value) <= max_chars:
        return value
    half = max_chars // 2
    omitted = len(value) - max_chars
    return f"{value[:half]}\n... [TRUNCATED {omitted} chars of logs] ...\n{value[-half:]}"


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
    if isinstance(value, list):
        items = [
            _truncate_data(
                item,
                max_chars=max_chars,
                max_list_items=max_list_items,
                max_dict_items=max_dict_items,
            )
            for item in value[:max_list_items]
        ]
        if len(value) > max_list_items:
            items.append({"_truncated_items": len(value) - max_list_items})
        return items
    if isinstance(value, tuple):
        items = [
            _truncate_data(
                item,
                max_chars=max_chars,
                max_list_items=max_list_items,
                max_dict_items=max_dict_items,
            )
            for item in value[:max_list_items]
        ]
        if len(value) > max_list_items:
            items.append({"_truncated_items": len(value) - max_list_items})
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


def _parse_json(value: str | None, name: str) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON for '{name}': {exc.msg}") from exc


def _as_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _format_bytes(raw: int | float | None) -> str:
    if raw is None:
        return "0 B"
    size = float(raw)
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} EB"


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
        if platform.system() == "Windows"
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


def _compose_prefix() -> list[str]:
    docker_binary = shutil.which("docker")
    if docker_binary:
        probe = subprocess.run(
            [docker_binary, "compose", "version"],
            capture_output=True,
            text=True,
        )
        if probe.returncode == 0:
            return [docker_binary, "compose"]

    legacy_binary = shutil.which("docker-compose")
    if legacy_binary:
        probe = subprocess.run([legacy_binary, "version"], capture_output=True, text=True)
        if probe.returncode == 0:
            return [legacy_binary]

    raise RuntimeError(
        "Docker Compose is not available. Install Docker Compose v2 or docker-compose."
    )


def _run_compose(args: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    prefix = _compose_prefix()
    full_command = prefix + args
    result = subprocess.run(full_command, capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout, result.stderr


def _docker_binary() -> str:
    docker_binary = shutil.which("docker")
    if docker_binary:
        return docker_binary
    raise RuntimeError("Docker CLI is not available. Install Docker to use this toolset.")


def _build_filter_args(filters: str | None) -> list[str]:
    parsed = _parse_json(filters, "filters") if filters else None
    if parsed is None:
        return []
    if not isinstance(parsed, dict):
        raise ValueError("'filters' must be a JSON object")

    args: list[str] = []
    for key, value in parsed.items():
        if isinstance(value, list):
            for item in value:
                args += ["--filter", f"{key}={item}"]
            continue
        if value is None:
            args += ["--filter", str(key)]
            continue
        if isinstance(value, bool):
            args += ["--filter", f"{key}={str(value).lower()}"]
            continue
        args += ["--filter", f"{key}={value}"]
    return args


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


def _parse_json_lines(stdout: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, line in enumerate(stdout.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON line {idx}: {exc.msg}") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected JSON object on line {idx}")
        rows.append(parsed)
    return rows


def _parse_ports_string(raw: str | None) -> dict[str, list[dict[str, str]]]:
    if not raw or raw.strip() in {"", "-"}:
        return {}

    ports: dict[str, list[dict[str, str]]] = {}
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue

        if "->" not in token:
            key = token if "/" in token else f"{token}/tcp"
            ports.setdefault(key, [])
            continue

        host, container = token.split("->", 1)
        host = host.strip()
        container = container.strip()
        key = container if "/" in container else f"{container}/tcp"

        host_ip = "0.0.0.0"
        host_port = host
        if ":" in host:
            maybe_ip, maybe_port = host.rsplit(":", 1)
            host_ip = maybe_ip or "0.0.0.0"
            host_port = maybe_port

        ports.setdefault(key, []).append({"HostIp": host_ip, "HostPort": host_port})
    return ports


def _parse_percent(value: Any) -> float:
    if value is None:
        return 0.0
    text = str(value).strip().rstrip("%")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _parse_size_to_bytes(value: Any) -> int:
    if value is None:
        return 0
    text = str(value).strip()
    if not text:
        return 0

    number_chars: list[str] = []
    unit_chars: list[str] = []
    for char in text:
        if char.isdigit() or char == ".":
            number_chars.append(char)
        elif not char.isspace():
            unit_chars.append(char)

    if not number_chars:
        return 0

    try:
        number = float("".join(number_chars))
    except ValueError:
        return 0

    unit = "".join(unit_chars).upper() or "B"
    multipliers = {
        "B": 1,
        "KB": 1000**1,
        "MB": 1000**2,
        "GB": 1000**3,
        "TB": 1000**4,
        "PB": 1000**5,
        "KIB": 1024**1,
        "MIB": 1024**2,
        "GIB": 1024**3,
        "TIB": 1024**4,
        "PIB": 1024**5,
    }
    multiplier = multipliers.get(unit)
    if multiplier is None:
        return 0
    return int(number * multiplier)


def _parse_two_sizes(raw: str | None) -> tuple[int, int]:
    if raw is None:
        return 0, 0
    parts = [part.strip() for part in str(raw).split("/", 1)]
    if len(parts) == 1:
        return _parse_size_to_bytes(parts[0]), 0
    return _parse_size_to_bytes(parts[0]), _parse_size_to_bytes(parts[1])


def _short_id(value: str | None, length: int = 12) -> str:
    if not value:
        return ""
    if value.startswith("sha256:"):
        return value.split(":", 1)[1][:length]
    return value[:length]


def _short_image_id(value: str | None, length: int = 12) -> str:
    if not value:
        return ""
    if value.startswith("sha256:"):
        digest = value.split(":", 1)[1]
        return f"sha256:{digest[:length]}"
    return value[:length]


def _inspect_first(args: list[str], error_label: str) -> dict[str, Any]:
    code, stdout, stderr = _run_safe_docker_cli(args)
    if code != 0:
        message = stderr.strip() or f"{error_label} failed (exit code {code})"
        raise RuntimeError(message)

    try:
        parsed = json.loads(stdout or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid inspect payload: {exc.msg}") from exc

    if not isinstance(parsed, list) or not parsed:
        raise ValueError("Inspect payload is empty")
    if not isinstance(parsed[0], dict):
        raise ValueError("Inspect payload item must be an object")
    return parsed[0]


def _container_metadata(container_id: str) -> tuple[str, str, str | None]:
    try:
        attrs = _inspect_first(
            ["inspect", "--type", "container", container_id],
            error_label="docker inspect container",
        )
    except Exception:
        return _short_id(container_id), container_id, None

    state = attrs.get("State", {})
    status = state.get("Status") if isinstance(state, dict) else None
    name = str(attrs.get("Name", container_id)).lstrip("/")
    return _short_id(str(attrs.get("Id", container_id))), name or container_id, status


class DockerBashInput(BaseModel):
    command: str = Field(description="Docker subcommand, for example: ps or compose ps")
    args: str | None = Field(default=None, description="Optional arguments for the command")
    cwd: str | None = Field(
        default=None,
        description="Optional working directory for compose commands",
    )
    timeout: int = Field(
        default=DOCKER_CLI_TIMEOUT_SECONDS, description="Command timeout in seconds"
    )


@tool(args_schema=DockerBashInput)
def docker_bash(
    command: str,
    args: str | None = None,
    cwd: str | None = None,
    timeout: int = DOCKER_CLI_TIMEOUT_SECONDS,
) -> str:
    """Execute whitelisted Docker CLI commands. Returns raw stdout on success, error string on failure."""
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
            return stdout
        return f"Error (exit {code}): {stderr.strip() or 'Command failed'}"
    except Exception as exc:
        return f"Error: {str(exc)}"


@tool
def list_containers(all_containers: bool = False, filters: str | None = None) -> str:
    """List containers."""
    try:
        command_args = ["ps"]
        if all_containers:
            command_args.append("-a")
        command_args += _build_filter_args(filters)

        code, stdout, stderr = _run_safe_docker_cli(command_args)
        if code != 0:
            message = stderr.strip() or f"docker ps failed (exit code {code})"
            return _error(message)
        return _ok(output=stdout)
    except Exception as exc:
        return _error(str(exc))


class RunContainerInput(BaseModel):
    image: str = Field(description="Image reference, for example 'nginx:latest'")
    name: str | None = Field(default=None, description="Optional container name")
    command: str | None = Field(default=None, description="Optional command")
    ports: str | None = Field(
        default=None,
        description='Port mappings as JSON: {"CONTAINER_PORT/tcp": HOST_PORT}. Example: {"80/tcp": 8000} maps container port 80 to host port 8000.',
    )
    environment: str | None = Field(default=None, description="JSON object or list for env vars")
    volumes: str | None = Field(default=None, description="JSON object of volume mappings")
    detach: bool = Field(default=True, description="Run in background")
    remove: bool = Field(default=False, description="Auto-remove on exit")
    network: str | None = Field(default=None, description="Optional network name")
    labels: str | None = Field(default=None, description="JSON object of labels")


@tool(args_schema=RunContainerInput)
def run_container(
    image: str,
    name: str | None = None,
    command: str | None = None,
    ports: str | None = None,
    environment: str | None = None,
    volumes: str | None = None,
    detach: bool = True,
    remove: bool = False,
    network: str | None = None,
    labels: str | None = None,
) -> str:
    """Run a new container from an image."""
    try:
        client = _docker_client()
        kwargs: dict[str, Any] = {
            "image": image,
            "detach": detach,
            "remove": remove,
        }

        if name:
            kwargs["name"] = name
        if command:
            kwargs["command"] = command
        if network:
            kwargs["network"] = network
        if ports:
            kwargs["ports"] = _parse_json(ports, "ports")
        if environment:
            kwargs["environment"] = _parse_json(environment, "environment")
        if volumes:
            kwargs["volumes"] = _parse_json(volumes, "volumes")
        if labels:
            kwargs["labels"] = _parse_json(labels, "labels")

        result = client.containers.run(**kwargs)

        if detach:
            return _ok(
                container_id=result.short_id,
                container_name=result.name,
                status=result.status,
            )

        return _ok(output=_as_text(result))
    except Exception as exc:
        return _error(str(exc))


@tool
def start_container(container_id: str) -> str:
    """Start a stopped container."""
    try:
        code, stdout, stderr = _run_safe_docker_cli(["start", container_id])
        if code != 0:
            message = stderr.strip() or f"docker start failed (exit code {code})"
            return _error(message)
        return _ok(output=stdout)
    except Exception as exc:
        return _error(str(exc))


@tool
def stop_container(container_id: str, timeout: int = 10) -> str:
    """Stop a running container."""
    try:
        code, stdout, stderr = _run_safe_docker_cli(
            ["stop", "--timeout", str(timeout), container_id]
        )
        if code != 0:
            message = stderr.strip() or f"docker stop failed (exit code {code})"
            return _error(message)
        return _ok(output=stdout)
    except Exception as exc:
        return _error(str(exc))


@tool
def restart_container(container_id: str, timeout: int = 10) -> str:
    """Restart a container."""
    try:
        code, stdout, stderr = _run_safe_docker_cli(
            ["restart", "--timeout", str(timeout), container_id]
        )
        if code != 0:
            message = stderr.strip() or f"docker restart failed (exit code {code})"
            return _error(message)
        return _ok(output=stdout)
    except Exception as exc:
        return _error(str(exc))


@tool
def remove_container(container_id: str, force: bool = False, remove_volumes: bool = False) -> str:
    """Remove a container."""
    try:
        client = _docker_client()
        container = client.containers.get(container_id)
        container.remove(force=force, v=remove_volumes)
        return _ok(container_id=container.short_id, container_name=container.name)
    except Exception as exc:
        return _error(str(exc))


@tool
def get_container_logs(
    container_id: str,
    tail: int = 100,
    timestamps: bool = False,
    since: str | None = None,
    until: str | None = None,
) -> str:
    """Fetch container logs."""
    try:
        command_args = ["logs", "--tail", str(tail)]
        if timestamps:
            command_args.append("--timestamps")
        if since:
            command_args += ["--since", since]
        if until:
            command_args += ["--until", until]
        command_args.append(container_id)

        code, stdout, stderr = _run_safe_docker_cli(command_args)
        if code != 0:
            message = stderr.strip() or f"docker logs failed (exit code {code})"
            return _error(message)
        return _ok(output=stdout)
    except Exception as exc:
        return _error(str(exc))


@tool
def get_container_stats(container_id: str) -> str:
    """Get one snapshot of container CPU and memory usage."""
    try:
        command_args = ["stats", "--no-stream", container_id]
        code, stdout, stderr = _run_safe_docker_cli(command_args)
        if code != 0:
            message = stderr.strip() or f"docker stats failed (exit code {code})"
            return _error(message)
        return _ok(output=stdout)
    except Exception as exc:
        return _error(str(exc))


class ExecInContainerInput(BaseModel):
    container_id: str = Field(description="Container ID or name")
    command: str = Field(description="Command to execute")
    workdir: str | None = Field(default=None, description="Working directory inside container")
    environment: str | None = Field(default=None, description="JSON object/list of env vars")
    user: str | None = Field(default=None, description="User inside container")
    privileged: bool = Field(default=False, description="Run with extended privileges")
    detach: bool = Field(default=False, description="Run detached")


@tool(args_schema=ExecInContainerInput)
def exec_in_container(
    container_id: str,
    command: str,
    workdir: str | None = None,
    environment: str | None = None,
    user: str | None = None,
    privileged: bool = False,
    detach: bool = False,
) -> str:
    """Execute a command in a container.

    For commands with shell operators (|, >, <, &, &&, ||), wrap in 'sh -c' manually:
    Example: exec_in_container(container_id="abc", command="sh -c 'echo test > /file.txt'")
    """
    import shlex

    try:
        client = _docker_client()
        container = client.containers.get(container_id)

        # Docker SDK handles string commands - pass as-is for proper quoted string handling
        cmd = command

        kwargs: dict[str, Any] = {
            "cmd": cmd,
            "detach": detach,
            "privileged": privileged,
        }
        if workdir:
            kwargs["workdir"] = workdir
        if environment:
            kwargs["environment"] = _parse_json(environment, "environment")
        if user:
            kwargs["user"] = user

        result = container.exec_run(**kwargs)

        if detach:
            return _ok(container_id=container.short_id, detached=True)

        return _ok(
            container_id=container.short_id,
            exit_code=result.exit_code,
            output=_as_text(result.output),
        )
    except Exception as exc:
        return _error(str(exc))


@tool
def inspect_container(container_id: str) -> str:
    """Inspect a container."""
    try:
        code, stdout, stderr = _run_safe_docker_cli(
            ["inspect", "--type", "container", container_id]
        )
        if code != 0:
            message = stderr.strip() or f"docker inspect container failed (exit code {code})"
            return _error(message)
        return _ok(output=stdout)
    except Exception as exc:
        return _error(str(exc))


@tool
def list_images(filters: str | None = None) -> str:
    """List local images."""
    try:
        command_args = ["images"]
        command_args += _build_filter_args(filters)

        code, stdout, stderr = _run_safe_docker_cli(command_args)
        if code != 0:
            message = stderr.strip() or f"docker images failed (exit code {code})"
            return _error(message)
        return _ok(output=stdout)
    except Exception as exc:
        return _error(str(exc))


@tool
def pull_image(image: str, tag: str = "latest") -> str:
    """Pull an image from a registry."""
    try:
        client = _docker_client()
        pulled = client.images.pull(repository=image, tag=tag)
        return _ok(image_id=pulled.short_id, tags=pulled.tags)
    except Exception as exc:
        return _error(str(exc))


class BuildImageInput(BaseModel):
    path: str = Field(default="/", description="Workspace-relative build context")
    tag: str | None = Field(default=None, description="Image tag")
    dockerfile: str = Field(default="Dockerfile", description="Dockerfile path relative to context")
    rm: bool = Field(default=True, description="Remove intermediate containers")
    pull: bool = Field(default=False, description="Always attempt to pull newer base images")
    nocache: bool = Field(default=False, description="Do not use cache")
    forcerm: bool = Field(default=False, description="Always remove intermediate containers")
    buildargs: str | None = Field(default=None, description="JSON object for build args")
    labels: str | None = Field(default=None, description="JSON object for image labels")
    target: str | None = Field(default=None, description="Target stage")


@tool(args_schema=BuildImageInput)
def build_image(
    path: str = "/",
    tag: str | None = None,
    dockerfile: str = "Dockerfile",
    rm: bool = True,
    pull: bool = False,
    nocache: bool = False,
    forcerm: bool = False,
    buildargs: str | None = None,
    labels: str | None = None,
    target: str | None = None,
) -> str:
    """Build an image from a Dockerfile in workspace."""
    try:
        client = _docker_client()

        context_path = _resolve_workspace_path(path)
        if not context_path.exists():
            return _error(f"Build context does not exist: {context_path}")

        kwargs: dict[str, Any] = {
            "path": str(context_path),
            "dockerfile": dockerfile,
            "rm": rm,
            "pull": pull,
            "nocache": nocache,
            "forcerm": forcerm,
            "tag": tag,
        }

        parsed_buildargs = _parse_json(buildargs, "buildargs") if buildargs else None
        parsed_labels = _parse_json(labels, "labels") if labels else None

        if parsed_buildargs is not None:
            kwargs["buildargs"] = parsed_buildargs
        if parsed_labels is not None:
            kwargs["labels"] = parsed_labels
        if target:
            kwargs["target"] = target

        image, logs = client.images.build(**kwargs)

        normalized_logs = []
        for item in logs:
            if isinstance(item, dict):
                if "stream" in item:
                    normalized_logs.append(item["stream"].strip())
                elif "error" in item:
                    normalized_logs.append(f"ERROR: {item['error']}")
                else:
                    normalized_logs.append(json.dumps(item, default=str))
            else:
                normalized_logs.append(_as_text(item))

        return _ok(
            image_id=image.short_id,
            tags=image.tags,
            build_context=str(context_path),
            logs=normalized_logs,
        )
    except Exception as exc:
        return _error(str(exc))


@tool
def remove_image(image: str, force: bool = False, noprune: bool = False) -> str:
    """Remove an image."""
    try:
        client = _docker_client()
        result = client.images.remove(image=image, force=force, noprune=noprune)
        return _ok(removed=image, details=result)
    except Exception as exc:
        return _error(str(exc))


@tool
def tag_image(image: str, repository: str, tag: str = "latest") -> str:
    """Tag an existing image."""
    try:
        client = _docker_client()
        image_obj = client.images.get(image)
        tagged = image_obj.tag(repository=repository, tag=tag)
        return _ok(image_id=image_obj.short_id, tagged=tagged, target=f"{repository}:{tag}")
    except Exception as exc:
        return _error(str(exc))


@tool
def inspect_image(image: str) -> str:
    """Inspect image metadata."""
    try:
        code, stdout, stderr = _run_safe_docker_cli(["inspect", "--type", "image", image])
        if code != 0:
            message = stderr.strip() or f"docker inspect image failed (exit code {code})"
            return _error(message)
        return _ok(output=stdout)
    except Exception as exc:
        return _error(str(exc))


@tool
def prune_images(dangling_only: bool = True) -> str:
    """Prune unused images."""
    try:
        client = _docker_client()
        filters = {"dangling": str(dangling_only).lower()}
        result = client.images.prune(filters=filters)
        return _ok(result=result)
    except Exception as exc:
        return _error(str(exc))


@tool
def list_networks(filters: str | None = None) -> str:
    """List Docker networks."""
    try:
        command_args = ["network", "ls"]
        command_args += _build_filter_args(filters)

        code, stdout, stderr = _run_safe_docker_cli(command_args)
        if code != 0:
            message = stderr.strip() or f"docker network ls failed (exit code {code})"
            return _error(message)
        return _ok(output=stdout)
    except Exception as exc:
        return _error(str(exc))


class CreateNetworkInput(BaseModel):
    name: str = Field(description="Network name")
    driver: str = Field(default="bridge", description="Network driver")
    attachable: bool = Field(default=False, description="Attachable network")
    internal: bool = Field(default=False, description="Internal-only network")
    labels: str | None = Field(default=None, description="JSON object of labels")
    options: str | None = Field(default=None, description="JSON object of driver options")
    ipam: str | None = Field(default=None, description="JSON object for IPAM config")


@tool(args_schema=CreateNetworkInput)
def create_network(
    name: str,
    driver: str = "bridge",
    attachable: bool = False,
    internal: bool = False,
    labels: str | None = None,
    options: str | None = None,
    ipam: str | None = None,
) -> str:
    """Create a network."""
    try:
        client = _docker_client()

        kwargs: dict[str, Any] = {
            "name": name,
            "driver": driver,
            "attachable": attachable,
            "internal": internal,
        }
        if labels:
            kwargs["labels"] = _parse_json(labels, "labels")
        if options:
            kwargs["options"] = _parse_json(options, "options")
        if ipam:
            kwargs["ipam"] = _parse_json(ipam, "ipam")

        network = client.networks.create(**kwargs)
        return _ok(network_id=network.short_id, network_name=network.name)
    except Exception as exc:
        return _error(str(exc))


@tool
def remove_network(network_id: str) -> str:
    """Remove a network."""
    try:
        client = _docker_client()
        network = client.networks.get(network_id)
        network_name = network.name
        network.remove()
        return _ok(network_id=network.short_id, network_name=network_name)
    except Exception as exc:
        return _error(str(exc))


@tool
def connect_to_network(
    network_id: str,
    container_id: str,
    aliases: str | None = None,
    links: str | None = None,
    driver_opts: str | None = None,
) -> str:
    """Connect a container to a network."""
    try:
        client = _docker_client()
        network = client.networks.get(network_id)
        container = client.containers.get(container_id)

        kwargs: dict[str, Any] = {}
        if aliases:
            kwargs["aliases"] = _parse_json(aliases, "aliases")
        if links:
            kwargs["links"] = _parse_json(links, "links")
        if driver_opts:
            kwargs["driver_opt"] = _parse_json(driver_opts, "driver_opts")

        network.connect(container=container, **kwargs)
        return _ok(network_id=network.short_id, network_name=network.name, container=container.name)
    except Exception as exc:
        return _error(str(exc))


@tool
def disconnect_from_network(network_id: str, container_id: str, force: bool = False) -> str:
    """Disconnect a container from a network."""
    try:
        client = _docker_client()
        network = client.networks.get(network_id)
        container = client.containers.get(container_id)
        network.disconnect(container=container, force=force)
        return _ok(network_id=network.short_id, network_name=network.name, container=container.name)
    except Exception as exc:
        return _error(str(exc))


@tool
def inspect_network(network_id: str) -> str:
    """Inspect a network."""
    try:
        code, stdout, stderr = _run_safe_docker_cli(["network", "inspect", network_id])
        if code != 0:
            message = stderr.strip() or f"docker network inspect failed (exit code {code})"
            return _error(message)
        return _ok(output=stdout)
    except Exception as exc:
        return _error(str(exc))


@tool
def list_volumes(filters: str | None = None) -> str:
    """List Docker volumes."""
    try:
        command_args = ["volume", "ls"]
        command_args += _build_filter_args(filters)

        code, stdout, stderr = _run_safe_docker_cli(command_args)
        if code != 0:
            message = stderr.strip() or f"docker volume ls failed (exit code {code})"
            return _error(message)
        return _ok(output=stdout)
    except Exception as exc:
        return _error(str(exc))


class CreateVolumeInput(BaseModel):
    name: str = Field(description="Volume name")
    driver: str = Field(default="local", description="Volume driver")
    labels: str | None = Field(default=None, description="JSON object of labels")
    driver_opts: str | None = Field(default=None, description="JSON object of driver options")


@tool(args_schema=CreateVolumeInput)
def create_volume(
    name: str,
    driver: str = "local",
    labels: str | None = None,
    driver_opts: str | None = None,
) -> str:
    """Create a named volume."""
    try:
        client = _docker_client()
        kwargs: dict[str, Any] = {"name": name, "driver": driver}
        if labels:
            kwargs["labels"] = _parse_json(labels, "labels")
        if driver_opts:
            kwargs["driver_opts"] = _parse_json(driver_opts, "driver_opts")

        volume = client.volumes.create(**kwargs)
        return _ok(volume_name=volume.name, details=volume.attrs)
    except Exception as exc:
        return _error(str(exc))


@tool
def remove_volume(name: str, force: bool = False) -> str:
    """Remove a named volume."""
    try:
        client = _docker_client()
        volume = client.volumes.get(name)
        volume.remove(force=force)
        return _ok(volume_name=name)
    except Exception as exc:
        return _error(str(exc))


@tool
def inspect_volume(name: str) -> str:
    """Inspect a volume."""
    try:
        code, stdout, stderr = _run_safe_docker_cli(["volume", "inspect", name])
        if code != 0:
            message = stderr.strip() or f"docker volume inspect failed (exit code {code})"
            return _error(message)
        return _ok(output=stdout)
    except Exception as exc:
        return _error(str(exc))


@tool
def prune_volumes() -> str:
    """Prune unused volumes."""
    try:
        client = _docker_client()
        result = client.volumes.prune()
        return _ok(result=result)
    except Exception as exc:
        return _error(str(exc))


@tool
def docker_system_info() -> str:
    """Get Docker daemon information."""
    try:
        code, stdout, stderr = _run_safe_docker_cli(["info", "--format", "json"])
        if code != 0:
            message = stderr.strip() or f"docker info failed (exit code {code})"
            return _error(message)
        return _ok(output=stdout)
    except Exception as exc:
        return _error(str(exc))


@tool
def docker_system_prune(
    all_resources: bool = False,
    volumes: bool = False,
    build_cache: bool = False,
) -> str:
    """Prune stopped containers, networks, images, and optional volumes/cache."""
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


@tool
def docker_version() -> str:
    """Get Docker version details."""
    try:
        code, stdout, stderr = _run_safe_docker_cli(["version", "--format", "json"])
        if code != 0:
            message = stderr.strip() or f"docker version failed (exit code {code})"
            return _error(message)
        return _ok(output=stdout)
    except Exception as exc:
        return _error(str(exc))


class ComposeUpInput(BaseModel):
    file_path: str = Field(default="/docker-compose.yml", description="Compose file in workspace")
    project_name: str | None = Field(default=None, description="Compose project name")
    detach: bool = Field(default=True, description="Run containers in background")
    build: bool = Field(default=False, description="Build images before starting")
    force_recreate: bool = Field(default=False, description="Recreate containers")
    remove_orphans: bool = Field(default=False, description="Remove orphan containers")
    services: str | None = Field(
        default=None, description="JSON list or comma-separated service names"
    )
    cwd: str | None = Field(default=None, description="Workspace-relative working directory")


def _parse_services(services: str | None) -> list[str]:
    if services is None or services.strip() == "":
        return []

    stripped = services.strip()
    if stripped.startswith("["):
        parsed = _parse_json(stripped, "services")
        if not isinstance(parsed, list):
            raise ValueError("'services' JSON must be a list")
        return [str(item) for item in parsed]

    return [item.strip() for item in stripped.split(",") if item.strip()]


def _compose_file_and_cwd(file_path: str, cwd: str | None) -> tuple[Path, Path]:
    compose_file = _resolve_workspace_path(file_path)
    if cwd:
        working_dir = _resolve_workspace_path(cwd)
    else:
        working_dir = compose_file.parent

    if not compose_file.exists():
        raise FileNotFoundError(f"Compose file not found: {compose_file}")
    if not working_dir.exists():
        raise FileNotFoundError(f"Compose working directory not found: {working_dir}")

    return compose_file, working_dir


@tool(args_schema=ComposeUpInput)
def compose_up(
    file_path: str = "/docker-compose.yml",
    project_name: str | None = None,
    detach: bool = True,
    build: bool = False,
    force_recreate: bool = False,
    remove_orphans: bool = False,
    services: str | None = None,
    cwd: str | None = None,
) -> str:
    """Run docker compose up."""
    try:
        compose_file, working_dir = _compose_file_and_cwd(file_path=file_path, cwd=cwd)
        service_list = _parse_services(services)

        args = ["-f", str(compose_file)]
        if project_name:
            args += ["-p", project_name]
        args += ["up"]
        if detach:
            args.append("-d")
        if build:
            args.append("--build")
        if force_recreate:
            args.append("--force-recreate")
        if remove_orphans:
            args.append("--remove-orphans")
        args += service_list

        code, stdout, stderr = _run_compose(args=args, cwd=str(working_dir))
        payload = {
            "exit_code": code,
            "stdout": stdout,
            "stderr": stderr,
            "compose_file": str(compose_file),
            "cwd": str(working_dir),
        }
        if code == 0:
            return _ok(**payload)
        return _error("docker compose up failed", **payload)
    except Exception as exc:
        return _error(str(exc))


class ComposeDownInput(BaseModel):
    file_path: str = Field(default="/docker-compose.yml", description="Compose file in workspace")
    project_name: str | None = Field(default=None, description="Compose project name")
    remove_orphans: bool = Field(default=False, description="Remove orphan containers")
    volumes: bool = Field(default=False, description="Remove named volumes")
    rmi: str | None = Field(default=None, description="Image removal policy: all|local")
    cwd: str | None = Field(default=None, description="Workspace-relative working directory")


@tool(args_schema=ComposeDownInput)
def compose_down(
    file_path: str = "/docker-compose.yml",
    project_name: str | None = None,
    remove_orphans: bool = False,
    volumes: bool = False,
    rmi: str | None = None,
    cwd: str | None = None,
) -> str:
    """Run docker compose down."""
    try:
        compose_file, working_dir = _compose_file_and_cwd(file_path=file_path, cwd=cwd)

        args = ["-f", str(compose_file)]
        if project_name:
            args += ["-p", project_name]
        args += ["down"]
        if remove_orphans:
            args.append("--remove-orphans")
        if volumes:
            args.append("-v")
        if rmi:
            if rmi not in {"all", "local"}:
                return _error("Invalid rmi value. Allowed values: all, local")
            args += ["--rmi", rmi]

        code, stdout, stderr = _run_compose(args=args, cwd=str(working_dir))
        payload = {
            "exit_code": code,
            "stdout": stdout,
            "stderr": stderr,
            "compose_file": str(compose_file),
            "cwd": str(working_dir),
        }
        if code == 0:
            return _ok(**payload)
        return _error("docker compose down failed", **payload)
    except Exception as exc:
        return _error(str(exc))


class ComposePsInput(BaseModel):
    file_path: str = Field(default="/docker-compose.yml", description="Compose file in workspace")
    project_name: str | None = Field(default=None, description="Compose project name")
    all_services: bool = Field(default=False, description="Include stopped services")
    format_json: bool = Field(default=True, description="Request JSON output")
    cwd: str | None = Field(default=None, description="Workspace-relative working directory")


@tool(args_schema=ComposePsInput)
def compose_ps(
    file_path: str = "/docker-compose.yml",
    project_name: str | None = None,
    all_services: bool = False,
    format_json: bool = True,
    cwd: str | None = None,
) -> str:
    """Run docker compose ps."""
    try:
        compose_file, working_dir = _compose_file_and_cwd(file_path=file_path, cwd=cwd)

        command_args = ["compose", "-f", str(compose_file)]
        if project_name:
            command_args += ["-p", project_name]
        command_args += ["ps"]
        if all_services:
            command_args.append("-a")
        if format_json:
            command_args += ["--format", "json"]

        code, stdout, stderr = _run_safe_docker_cli(args=command_args, cwd=str(working_dir))
        payload = {"output": stdout}
        if code == 0:
            return _ok(**payload)
        return _error(stderr.strip() or "docker compose ps failed", **payload)
    except Exception as exc:
        return _error(str(exc))


class ComposeLogsInput(BaseModel):
    file_path: str = Field(default="/docker-compose.yml", description="Compose file in workspace")
    project_name: str | None = Field(default=None, description="Compose project name")
    service: str | None = Field(default=None, description="Single service name")
    tail: int = Field(default=100, description="Number of lines")
    follow: bool = Field(default=False, description="Stream logs")
    timestamps: bool = Field(default=False, description="Include timestamps")
    cwd: str | None = Field(default=None, description="Workspace-relative working directory")


@tool(args_schema=ComposeLogsInput)
def compose_logs(
    file_path: str = "/docker-compose.yml",
    project_name: str | None = None,
    service: str | None = None,
    tail: int = 100,
    follow: bool = False,
    timestamps: bool = False,
    cwd: str | None = None,
) -> str:
    """Run docker compose logs."""
    try:
        compose_file, working_dir = _compose_file_and_cwd(file_path=file_path, cwd=cwd)

        command_args = ["compose", "-f", str(compose_file)]
        if project_name:
            command_args += ["-p", project_name]
        command_args += ["logs", "--tail", str(tail)]
        if follow:
            command_args.append("-f")
        if timestamps:
            command_args.append("-t")
        if service:
            command_args.append(service)

        code, stdout, stderr = _run_safe_docker_cli(args=command_args, cwd=str(working_dir))
        payload = {"output": stdout}
        if code == 0:
            return _ok(**payload)
        return _error(stderr.strip() or "docker compose logs failed", **payload)
    except Exception as exc:
        return _error(str(exc))


CONTAINER_TOOLS = [
    list_containers,
    run_container,
    start_container,
    stop_container,
    restart_container,
    remove_container,
    get_container_logs,
    get_container_stats,
    exec_in_container,
    inspect_container,
]

IMAGE_TOOLS = [
    list_images,
    pull_image,
    build_image,
    remove_image,
    tag_image,
    inspect_image,
    prune_images,
]

NETWORK_TOOLS = [
    list_networks,
    create_network,
    remove_network,
    connect_to_network,
    disconnect_from_network,
    inspect_network,
]

VOLUME_TOOLS = [
    list_volumes,
    create_volume,
    remove_volume,
    inspect_volume,
    prune_volumes,
]

SYSTEM_TOOLS = [
    docker_system_info,
    docker_system_prune,
    docker_version,
]

COMPOSE_TOOLS = [
    compose_up,
    compose_down,
    compose_ps,
    compose_logs,
]

AGENT_SAFE_TOOLS = [docker_bash]

AGENT_SDK_TOOLS = [
    run_container,
    pull_image,
    build_image,
    tag_image,
    create_network,
    create_volume,
    connect_to_network,
    disconnect_from_network,
    exec_in_container,
    compose_up,
    compose_down,
]

AGENT_DANGEROUS_SDK_TOOLS = [
    remove_image,
    prune_images,
    remove_container,
    remove_network,
    remove_volume,
    prune_volumes,
    docker_system_prune,
]

ALL_DOCKER_TOOLS = AGENT_SAFE_TOOLS + AGENT_SDK_TOOLS + AGENT_DANGEROUS_SDK_TOOLS

__all__ = [
    "docker_bash",
    "list_containers",
    "run_container",
    "start_container",
    "stop_container",
    "restart_container",
    "remove_container",
    "get_container_logs",
    "get_container_stats",
    "exec_in_container",
    "inspect_container",
    "list_images",
    "pull_image",
    "build_image",
    "remove_image",
    "tag_image",
    "inspect_image",
    "prune_images",
    "list_networks",
    "create_network",
    "remove_network",
    "connect_to_network",
    "disconnect_from_network",
    "inspect_network",
    "list_volumes",
    "create_volume",
    "remove_volume",
    "inspect_volume",
    "prune_volumes",
    "docker_system_info",
    "docker_system_prune",
    "docker_version",
    "compose_up",
    "compose_down",
    "compose_ps",
    "compose_logs",
    "CONTAINER_TOOLS",
    "IMAGE_TOOLS",
    "NETWORK_TOOLS",
    "VOLUME_TOOLS",
    "SYSTEM_TOOLS",
    "COMPOSE_TOOLS",
    "AGENT_SAFE_TOOLS",
    "AGENT_SDK_TOOLS",
    "AGENT_DANGEROUS_SDK_TOOLS",
    "ALL_DOCKER_TOOLS",
]
