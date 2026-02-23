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
    provider_sort: str | None = None,
    request_timeout: float | None = None,
    max_retries: int = 2,
) -> ChatOpenAI:
    configured = model or os.getenv("OPENROUTER_MODEL") or "openai/gpt-4o-mini"
    model_name = configured.replace("openrouter/", "")

    config: dict[str, Any] = {
        "model": model_name,
        "temperature": temperature,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": api_key or os.getenv("OPENROUTER_API_KEY"),
        "default_headers": {
            "HTTP-Referer": "https://github.com/htooayelwinict/attalang",
            "X-Title": app_title,
        },
        "request_timeout": request_timeout or float(
            os.getenv("OPENROUTER_REQUEST_TIMEOUT", "120")
        ),
        "max_retries": max_retries,
    }

    # Merge provider_sort into extra_body for OpenRouter routing
    body = extra_body.copy() if extra_body else {}
    if provider_sort:
        body.setdefault("provider", {})["sort"] = provider_sort

    if body:
        config["extra_body"] = body

    return ChatOpenAI(**config)
