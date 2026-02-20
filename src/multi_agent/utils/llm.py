import os
from typing import Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def create_openrouter_llm(
    model: str | None = None,
    temperature: float = 0.0,
    api_key: str | None = None,
    app_title: str = "MultiAgentDocker",
    extra_body: dict[str, Any] | None = None,
) -> ChatOpenAI:
    configured = model or os.getenv("OPENROUTER_MODEL") or "openai/gpt-4o-mini"
    model_name = configured.replace("openrouter/", "")

    config: dict[str, Any] = {
        "model": model_name,
        "temperature": temperature,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": api_key or os.getenv("OPENROUTER_API_KEY"),
        "default_headers": {
            "HTTP-Referer": "https://github.com/lewisae/deepagent",
            "X-Title": app_title,
        },
    }

    if extra_body:
        config["extra_body"] = extra_body

    return ChatOpenAI(**config)
