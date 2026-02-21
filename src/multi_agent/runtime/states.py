from typing import Literal

from pydantic import BaseModel, ConfigDict


class CoordinatorState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: Literal["cli"] | None = None
    user_input: str | None = None
    route: Literal["docker"] | None = None
    docker_request: str | None = None
    docker_response: str | None = None
    final_response: str | None = None
    thread_id: str | None = None
    error: str | None = None


class DockerWorkerState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: str | None = None
    response: str | None = None
    thread_id: str | None = None
    error: str | None = None
