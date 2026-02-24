"""Tests for the V3 Programmatic Docker Agent — bridge, executor, and agent."""

import pytest

from src.multi_agent_v3.tools.bridge import ProgrammaticToolBridge
from src.multi_agent_v3.tools.executor import CodeExecutor


# ---------------------------------------------------------------------------
# ProgrammaticToolBridge tests
# ---------------------------------------------------------------------------

class TestProgrammaticToolBridge:
    def test_register_langchain_tool(self):
        """Bridge registers a LangChain tool and exposes it as a callable."""
        from src.multi_agent.tools.docker_tools import docker_cli

        bridge = ProgrammaticToolBridge()
        bridge.register_langchain_tool(docker_cli)

        assert "docker_cli" in bridge.tool_names
        assert "docker_cli" in bridge.callables

    def test_register_many(self):
        from src.multi_agent.tools.docker_tools import docker_cli

        bridge = ProgrammaticToolBridge()
        bridge.register_many([docker_cli])

        assert len(bridge.tool_names) == 1

    def test_api_reference_contains_signature(self):
        from src.multi_agent.tools.docker_tools import docker_cli

        bridge = ProgrammaticToolBridge()
        bridge.register_langchain_tool(docker_cli)
        ref = bridge.get_api_reference()

        assert "docker_cli(" in ref
        assert "command" in ref

    def test_make_namespace(self):
        from src.multi_agent.tools.docker_tools import docker_cli

        bridge = ProgrammaticToolBridge()
        bridge.register_langchain_tool(docker_cli)
        ns = bridge.make_namespace()

        assert "docker_cli" in ns
        assert callable(ns["docker_cli"])


# ---------------------------------------------------------------------------
# CodeExecutor tests
# ---------------------------------------------------------------------------

class TestCodeExecutor:
    def test_basic_print(self):
        """Executor captures print() output."""
        executor = CodeExecutor(tool_namespace={}, timeout_seconds=5)
        result = executor.execute('print("hello world")')
        assert "hello world" in result

    def test_loop_execution(self):
        """Executor supports loops."""
        executor = CodeExecutor(tool_namespace={}, timeout_seconds=5)
        result = executor.execute(
            "for i in range(3):\n    print(f'item {i}')"
        )
        assert "item 0" in result
        assert "item 1" in result
        assert "item 2" in result

    def test_variable_and_conditional(self):
        executor = CodeExecutor(tool_namespace={}, timeout_seconds=5)
        code = """
x = 10
if x > 5:
    print("big")
else:
    print("small")
"""
        result = executor.execute(code)
        assert "big" in result

    def test_json_import_allowed(self):
        executor = CodeExecutor(tool_namespace={}, timeout_seconds=5)
        code = """
import json
data = {"key": "value"}
print(json.dumps(data))
"""
        result = executor.execute(code)
        assert '"key"' in result

    def test_os_import_blocked(self):
        executor = CodeExecutor(tool_namespace={}, timeout_seconds=5)
        result = executor.execute("import os\nprint(os.getcwd())")
        assert "[ERROR]" in result
        assert "not allowed" in result

    def test_subprocess_import_blocked(self):
        executor = CodeExecutor(tool_namespace={}, timeout_seconds=5)
        result = executor.execute("import subprocess\nsubprocess.run(['ls'])")
        assert "[ERROR]" in result

    def test_open_blocked(self):
        """open() is not in safe builtins."""
        executor = CodeExecutor(tool_namespace={}, timeout_seconds=5)
        result = executor.execute("f = open('/etc/passwd')\nprint(f.read())")
        assert "[ERROR]" in result

    def test_tool_injection(self):
        """Injected tools are callable from code."""
        def mock_docker_cli(command: str = "", args: str | None = None, **kwargs) -> str:
            return f"OK: {command} {args or ''}"

        executor = CodeExecutor(
            tool_namespace={"docker_cli": mock_docker_cli},
            timeout_seconds=5,
        )
        result = executor.execute(
            'result = docker_cli(command="ps", args="-a")\nprint(result)'
        )
        assert "OK: ps -a" in result

    def test_multi_tool_calls(self):
        """Multiple tool calls work within one code block."""
        call_log: list[str] = []

        def mock_docker_cli(command: str = "", args: str | None = None, **kwargs) -> str:
            call_log.append(f"{command} {args or ''}")
            return f"done: {command}"

        executor = CodeExecutor(
            tool_namespace={"docker_cli": mock_docker_cli},
            timeout_seconds=5,
        )
        code = """
for cmd in ["pull redis:alpine", "pull nginx:alpine", "pull postgres:15"]:
    parts = cmd.split(" ", 1)
    result = docker_cli(command=parts[0], args=parts[1])
    print(result)
"""
        result = executor.execute(code)
        assert len(call_log) == 3
        assert "done: pull" in result

    def test_no_output_message(self):
        executor = CodeExecutor(tool_namespace={}, timeout_seconds=5)
        result = executor.execute("x = 42")
        assert "[No output" in result

    def test_output_truncation(self):
        executor = CodeExecutor(tool_namespace={}, timeout_seconds=5, max_output_chars=100)
        result = executor.execute("print('A' * 500)")
        assert "TRUNCATED" in result

    def test_timeout_protection(self):
        """Infinite loops are caught by timeout."""
        executor = CodeExecutor(tool_namespace={}, timeout_seconds=1)
        result = executor.execute("while True: pass")
        assert "TIMEOUT" in result

    def test_exception_in_code(self):
        executor = CodeExecutor(tool_namespace={}, timeout_seconds=5)
        result = executor.execute("raise ValueError('test error')")
        assert "[ERROR]" in result
        assert "test error" in result


# ---------------------------------------------------------------------------
# Integration: Bridge -> Executor
# ---------------------------------------------------------------------------

class TestBridgeExecutorIntegration:
    def test_bridge_tools_work_in_executor(self):
        """End-to-end: register a tool via bridge, call it via executor."""
        def fake_docker(command: str = "", args: str | None = None, **kwargs) -> str:
            return f"EXECUTED: docker {command} {args or ''}"

        # Simulate what the bridge does
        bridge = ProgrammaticToolBridge()
        # Manually add a plain function (not LangChain tool) for testing
        bridge._callables["docker_cli"] = lambda **kw: fake_docker(**kw)
        bridge._signatures["docker_cli"] = "docker_cli(command: str, args: str | None) -> str"
        bridge._descriptions["docker_cli"] = "Execute Docker CLI commands"

        executor = CodeExecutor(
            tool_namespace=bridge.make_namespace(),
            timeout_seconds=5,
        )

        code = """
result = docker_cli(command="ps", args="-a")
print(result)
"""
        output = executor.execute(code)
        assert "EXECUTED: docker ps -a" in output
