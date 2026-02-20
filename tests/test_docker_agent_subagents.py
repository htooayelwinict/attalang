from src.multi_agent.agents import DockerAgent
from src.multi_agent.tools import list_containers


def test_docker_agent_defaults_to_subagent_mode() -> None:
    agent = DockerAgent()

    assert agent.tools == []
    assert len(agent.subagents) == 6

    subagent_names = [subagent["name"] for subagent in agent.subagents]
    assert subagent_names == [
        "container-agent",
        "image-agent",
        "network-agent",
        "volume-agent",
        "compose-agent",
        "system-agent",
    ]

    tool_counts = {subagent["name"]: len(subagent["tools"]) for subagent in agent.subagents}
    assert tool_counts == {
        "container-agent": 10,
        "image-agent": 7,
        "network-agent": 6,
        "volume-agent": 5,
        "compose-agent": 4,
        "system-agent": 3,
    }


def test_docker_agent_back_compat_custom_tools_mode() -> None:
    agent = DockerAgent(tools=[list_containers])

    assert len(agent.tools) == 1
    assert agent.subagents == []
