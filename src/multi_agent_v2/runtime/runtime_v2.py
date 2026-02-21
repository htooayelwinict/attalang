import asyncio
from dataclasses import dataclass
from typing import Any, Iterator

from src.multi_agent_v2.agents import DockerAgentV2, create_docker_agent_v2


@dataclass
class DockerRuntimeV2:
    worker: DockerAgentV2

    @classmethod
    def create(
        cls,
        model: Any = None,
        temperature: float = 0.0,
        workspace_dir: str | None = None,
        skills_dir: str | None = None,
        instructions: str | None = None,
    ) -> "DockerRuntimeV2":
        worker = create_docker_agent_v2(
            model=model,
            temperature=temperature,
            workspace_dir=workspace_dir,
            skills_dir=skills_dir,
            instructions=instructions,
        )
        return cls(worker=worker)

    def run_turn(self, user_input: str, thread_id: str) -> str:
        if not user_input.strip():
            return "Empty input."

        try:
            return self.worker.invoke(user_input, thread_id=thread_id)
        except Exception as exc:
            return f"Docker worker error: {exc}"

    async def arun_turn(self, user_input: str, thread_id: str) -> str:
        if not user_input.strip():
            return "Empty input."

        try:
            return await self.worker.ainvoke(user_input, thread_id=thread_id)
        except Exception as exc:
            return f"Docker worker error: {exc}"

    def run_turn_verbose(self, user_input: str, thread_id: str) -> Iterator[str]:
        """Run with verbose output showing each step."""
        if not user_input.strip():
            yield "Empty input."
            return

        try:
            for event in self.worker.stream(user_input, thread_id=thread_id):
                yield event

            # Show todos after execution
            todos = self.worker.get_todos(thread_id)
            if todos:
                yield "\n[Plan]"
                for todo in todos:
                    status = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]"}.get(
                        getattr(todo, "status", "pending"), "[ ]"
                    )
                    content = getattr(todo, "content", str(todo))
                    yield f"  {status} {content}"

        except Exception as exc:
            yield f"Docker worker error: {exc}"


def create_docker_runtime_v2(
    model: Any = None,
    temperature: float = 0.0,
    workspace_dir: str | None = None,
    skills_dir: str | None = None,
    instructions: str | None = None,
) -> DockerRuntimeV2:
    return DockerRuntimeV2.create(
        model=model,
        temperature=temperature,
        workspace_dir=workspace_dir,
        skills_dir=skills_dir,
        instructions=instructions,
    )
