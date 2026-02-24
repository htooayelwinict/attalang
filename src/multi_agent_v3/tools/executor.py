"""Restricted Python code executor for programmatic tool calling.

Runs LLM-generated Python code via exec() with:
- Tool functions injected into namespace
- Restricted builtins (no file I/O, no dynamic imports, no eval/exec)
- Captured stdout via print() override
- Signal-based timeout (Unix only)
"""

from __future__ import annotations

import signal
import sys
import threading
import traceback
from io import StringIO
from typing import Any


# Builtins allowed inside the sandbox
_SAFE_BUILTINS: dict[str, Any] = {
    # Types
    "True": True,
    "False": False,
    "None": None,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "frozenset": frozenset,
    "bytes": bytes,
    "type": type,
    # Iteration / functional
    "range": range,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "sorted": sorted,
    "reversed": reversed,
    "len": len,
    "min": min,
    "max": max,
    "sum": sum,
    "any": any,
    "all": all,
    "abs": abs,
    "round": round,
    # String / repr
    "repr": repr,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "hasattr": hasattr,
    "getattr": getattr,
    "setattr": setattr,
    # Exceptions
    "Exception": Exception,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "KeyError": KeyError,
    "IndexError": IndexError,
    "RuntimeError": RuntimeError,
    "StopIteration": StopIteration,
}

# Modules allowed via __import__ inside sandbox
_ALLOWED_MODULES: frozenset[str] = frozenset({
    "json",
    "re",
    "time",
    "textwrap",
    "itertools",
    "functools",
    "collections",
})


class ExecutionTimeout(Exception):
    pass


class CodeExecutor:
    """Execute Python code with injected tool namespace and safety restrictions."""

    def __init__(
        self,
        tool_namespace: dict[str, Any],
        timeout_seconds: int = 120,
        max_output_chars: int = 8000,
    ) -> None:
        self._tool_namespace = tool_namespace
        self._timeout = timeout_seconds
        self._max_output = max_output_chars

    def execute(self, code: str) -> str:
        """Execute Python code and return captured stdout + return info.

        Returns:
            String with all print() output captured during execution.
            On error, returns the traceback.
        """
        output_buffer = StringIO()

        # Build restricted namespace
        namespace: dict[str, Any] = {}

        # Inject safe builtins
        safe_builtins = dict(_SAFE_BUILTINS)

        # Custom print that captures to buffer
        def _safe_print(*args: Any, sep: str = " ", end: str = "\n", **_: Any) -> None:
            text = sep.join(str(a) for a in args) + end
            output_buffer.write(text)

        safe_builtins["print"] = _safe_print

        # Restricted __import__
        def _safe_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name not in _ALLOWED_MODULES:
                raise ImportError(
                    f"Module '{name}' is not allowed. Allowed: {', '.join(sorted(_ALLOWED_MODULES))}"
                )
            return __builtins__["__import__"](name, *args, **kwargs) if isinstance(__builtins__, dict) else __import__(name, *args, **kwargs)

        safe_builtins["__import__"] = _safe_import

        namespace["__builtins__"] = safe_builtins

        # Inject tool functions
        namespace.update(self._tool_namespace)

        # Execute with timeout
        try:
            compiled = compile(code, "<programmatic_tools>", "exec")
            is_main = threading.current_thread() is threading.main_thread()
            if is_main and sys.platform != "win32":
                self._exec_with_signal_timeout(compiled, namespace)
            else:
                self._exec_with_thread_timeout(compiled, namespace)
        except ExecutionTimeout:
            output_buffer.write(f"\n[TIMEOUT] Code execution exceeded {self._timeout}s limit\n")
        except Exception:
            tb = traceback.format_exc()
            output_buffer.write(f"\n[ERROR]\n{tb}\n")

        result = output_buffer.getvalue()
        if len(result) > self._max_output:
            half = self._max_output // 2
            omitted = len(result) - self._max_output
            result = f"{result[:half]}\n... [TRUNCATED {omitted} chars] ...\n{result[-half:]}"

        return result or "[No output — use print() to see results]"

    def _exec_with_thread_timeout(self, compiled: Any, namespace: dict[str, Any]) -> None:
        """Execute with threading-based timeout (works from any thread)."""
        exc_holder: list[BaseException] = []

        def _target() -> None:
            try:
                exec(compiled, namespace)  # noqa: S102
            except Exception as e:
                exc_holder.append(e)

        t = threading.Thread(target=_target, daemon=True)
        t.start()
        t.join(timeout=self._timeout)
        if t.is_alive():
            raise ExecutionTimeout(f"Execution exceeded {self._timeout}s")
        if exc_holder:
            raise exc_holder[0]

    def _exec_with_signal_timeout(self, compiled: Any, namespace: dict[str, Any]) -> None:
        """Execute with signal-based timeout (main thread, Unix only)."""
        def _handler(signum: int, frame: Any) -> None:
            raise ExecutionTimeout(f"Execution exceeded {self._timeout}s")

        old_handler = signal.signal(signal.SIGALRM, _handler)
        signal.alarm(self._timeout)
        try:
            exec(compiled, namespace)  # noqa: S102
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
