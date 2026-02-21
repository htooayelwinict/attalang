from pathlib import Path

import pytest

from src.multi_agent_v2.agents import DockerAgentV2
from src.multi_agent_v2.agents import docker_agent_v2 as docker_agent_v2_module


class FakeFilesystemBackend:
    def __init__(self, root_dir: str, virtual_mode: bool = False):
        self.root_dir = root_dir
        self.virtual_mode = virtual_mode


class FakeAgent:
    def __init__(self) -> None:
        self.registered_tools: list[str] = []
        self.run_calls: list[tuple[str, object]] = []

    def tool(self, fn=None):
        if fn is None:
            def decorator(real_fn):
                self.registered_tools.append(real_fn.__name__)
                return real_fn

            return decorator

        self.registered_tools.append(fn.__name__)
        return fn

    async def run(self, message: str, deps=None):
        self.run_calls.append((message, deps))

        class Result:
            output = f"ok:{message}"

        return Result()


def _fake_loader(fake_agent: FakeAgent):
    def create_deep_agent(**_: object) -> FakeAgent:
        return fake_agent

    def create_default_deps(backend: object) -> dict[str, object]:
        return {"backend": backend}

    return {
        "create_deep_agent": create_deep_agent,
        "create_default_deps": create_default_deps,
        "DeepAgentDeps": None,
        "FilesystemBackend": FakeFilesystemBackend,
    }


def test_v2_constructor_defaults_without_optional_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_MODEL", "qwen/qwen3-coder-next")
    agent = DockerAgentV2()

    assert agent.agent is None
    assert len(agent.tools) == len(docker_agent_v2_module.ALL_DOCKER_TOOLS)
    assert agent._model == "qwen/qwen3-coder-next"
    assert str(agent.workspace_dir).endswith("/tmp/multi-agent-docker-v2-workspace")


@pytest.mark.asyncio
async def test_v2_missing_dependency_error_on_first_invoke(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_MODEL", "qwen/qwen3-coder-next")
    agent = DockerAgentV2()

    with pytest.raises(RuntimeError, match='pip install -e "\\.\\[agentv2,dev\\]"'):
        await agent.ainvoke("list containers")


def test_v2_requires_model_from_env_or_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

    with pytest.raises(RuntimeError, match="OPENROUTER_MODEL"):
        DockerAgentV2()


@pytest.mark.asyncio
async def test_v2_registers_all_tools_and_reuses_thread_deps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OPENROUTER_MODEL", "qwen/qwen3-coder-next")
    fake_agent = FakeAgent()
    monkeypatch.setattr(
        docker_agent_v2_module,
        "_load_pydantic_modules",
        lambda: _fake_loader(fake_agent),
    )

    agent = DockerAgentV2(workspace_dir=tmp_path)

    out1 = await agent.ainvoke("first", thread_id="thread-a")
    out2 = await agent.ainvoke("second", thread_id="thread-a")
    out3 = await agent.ainvoke("third", thread_id="thread-b")

    assert out1 == "ok:first"
    assert out2 == "ok:second"
    assert out3 == "ok:third"
    assert len(fake_agent.registered_tools) == len(docker_agent_v2_module.ALL_DOCKER_TOOLS)

    deps_a_first = fake_agent.run_calls[0][1]
    deps_a_second = fake_agent.run_calls[1][1]
    deps_b_first = fake_agent.run_calls[2][1]

    assert deps_a_first is deps_a_second
    assert deps_b_first is not deps_a_first
    assert len(agent.deps_by_thread) == 2


@pytest.mark.asyncio
async def test_v2_invoke_requires_ainvoke_when_loop_is_running(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OPENROUTER_MODEL", "qwen/qwen3-coder-next")
    fake_agent = FakeAgent()
    monkeypatch.setattr(
        docker_agent_v2_module,
        "_load_pydantic_modules",
        lambda: _fake_loader(fake_agent),
    )

    agent = DockerAgentV2(workspace_dir=tmp_path)

    with pytest.raises(RuntimeError, match="Use await DockerAgentV2.ainvoke"):
        agent.invoke("docker ps")
