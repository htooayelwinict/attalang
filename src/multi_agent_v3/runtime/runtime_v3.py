"""Runtime wrapper for the Programmatic Docker Agent.

Thin wrapper that mirrors V1's DockerGraphRuntime interface but uses the
programmatic agent (code execution) instead of the standard tool-calling agent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.multi_agent_v3.agents import create_programmatic_docker_agent, ProgrammaticDockerAgent


@dataclass
class ProgrammaticDockerRuntime:
    """Runtime that wraps ProgrammaticDockerAgent with the same interface as V1."""

    agent: ProgrammaticDockerAgent

    @classmethod
    def create(
        cls,
        model: str | None = None,
        temperature: float = 0.0,
        workspace_dir: str | None = None,
        app_title: str = "MultiAgentDockerProg",
        provider_sort: str | None = None,
    ) -> ProgrammaticDockerRuntime:
        agent = create_programmatic_docker_agent(
            model=model,
            temperature=temperature,
            workspace_dir=workspace_dir,
            app_title=app_title,
            provider_sort=provider_sort,
        )
        return cls(agent=agent)

    def run_turn(
        self,
        user_input: str,
        thread_id: str,
        callbacks: list[Any] | None = None,
    ) -> str:
        normalized = user_input.strip()
        if not normalized:
            return "Empty input."
        return self.agent.invoke(normalized, thread_id=thread_id, callbacks=callbacks)


def create_programmatic_runtime(
    model: str | None = None,
    temperature: float = 0.0,
    workspace_dir: str | None = None,
    app_title: str = "MultiAgentDockerProg",
    provider_sort: str | None = None,
) -> ProgrammaticDockerRuntime:
    return ProgrammaticDockerRuntime.create(
        model=model,
        temperature=temperature,
        workspace_dir=workspace_dir,
        app_title=app_title,
        provider_sort=provider_sort,
    )
