from typing import Literal, TypedDict


class CoordinatorState(TypedDict, total=False):
    origin: Literal["cli"]
    user_input: str
    route: Literal["docker"]
    docker_request: str
    docker_response: str
    final_response: str
    thread_id: str
    error: str


class DockerWorkerState(TypedDict, total=False):
    request: str
    response: str
    thread_id: str
    error: str
