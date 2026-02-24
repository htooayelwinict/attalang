"""Bridge that converts LangChain @tool functions into plain callables.

Strips LangChain wrappers so that tools can be called as regular Python functions
inside exec()-based code execution.
"""

from __future__ import annotations

import inspect
import textwrap
from typing import Any, Callable

from langchain_core.tools import BaseTool


class ProgrammaticToolBridge:
    """Converts LangChain tools to plain-function callables for programmatic use."""

    def __init__(self) -> None:
        self._callables: dict[str, Callable[..., str]] = {}
        self._signatures: dict[str, str] = {}
        self._descriptions: dict[str, str] = {}

    def register_langchain_tool(self, tool: BaseTool) -> None:
        """Register a LangChain @tool as a plain callable."""
        name = tool.name

        def _call(**kwargs: Any) -> str:
            return tool.invoke(kwargs)

        # Build a friendly signature from the tool's args_schema
        sig_parts: list[str] = []
        schema = tool.args_schema
        if schema:
            for field_name, field_info in schema.model_fields.items():
                annotation = field_info.annotation
                type_name = getattr(annotation, "__name__", str(annotation))
                if field_info.default is not None:
                    sig_parts.append(f"{field_name}: {type_name} = {field_info.default!r}")
                else:
                    sig_parts.append(f"{field_name}: {type_name}")

        self._callables[name] = _call
        self._signatures[name] = f"{name}({', '.join(sig_parts)}) -> str"
        self._descriptions[name] = tool.description or ""

    def register_many(self, tools: list[BaseTool]) -> None:
        for t in tools:
            self.register_langchain_tool(t)

    @property
    def callables(self) -> dict[str, Callable[..., str]]:
        return dict(self._callables)

    @property
    def tool_names(self) -> list[str]:
        return list(self._callables.keys())

    def get_api_reference(self) -> str:
        """Generate a human-readable API reference for all registered tools."""
        lines: list[str] = []
        for name in self._callables:
            sig = self._signatures[name]
            desc = self._descriptions[name]
            lines.append(f"  {sig}")
            if desc:
                # Indent description under signature
                wrapped = textwrap.fill(desc, width=90, initial_indent="    ", subsequent_indent="    ")
                lines.append(wrapped)
            lines.append("")
        return "\n".join(lines)

    def make_namespace(self) -> dict[str, Any]:
        """Build namespace dict for injection into exec().

        Each tool becomes a callable that accepts keyword arguments:
            result = docker_cli(command="ps", args="-a")
        """
        ns: dict[str, Any] = {}
        for name, fn in self._callables.items():
            ns[name] = fn
        return ns
