"""Tests for trajectory collector, models, and summarizer."""

import json
import time
import uuid

import pytest

from src.multi_agent.trajectory.collector import TrajectoryCollector
from src.multi_agent.trajectory.models import (
    DockerCliArgs,
    LLMCallRecord,
    ToolCallRecord,
    TrajectoryMetrics,
    TrajectoryRecord,
)
from src.multi_agent.trajectory.summary import summarize_trajectory, trajectory_to_dict


# ── model tests ─────────────────────────────────────────────────────


class TestDockerCliArgs:
    def test_basic_fields(self):
        args = DockerCliArgs(
            command="ps",
            args="-a",
            cwd=None,
            timeout=30,
            full_command="docker ps -a",
        )
        assert args.command == "ps"
        assert args.args == "-a"
        assert args.full_command == "docker ps -a"

    def test_compose_command(self):
        args = DockerCliArgs(
            command="compose up",
            args="-d --build",
            cwd="/workspace",
            timeout=60,
            full_command="docker compose up -d --build",
        )
        assert args.command == "compose up"
        assert args.cwd == "/workspace"


class TestToolCallRecord:
    def test_successful_record(self):
        r = ToolCallRecord(
            tool="docker_cli",
            input_raw='{"command":"ps","args":"-a"}',
            input_parsed={"command": "ps", "args": "-a"},
            docker_cli_args=DockerCliArgs(
                command="ps", args="-a", full_command="docker ps -a"
            ),
            output="CONTAINER ID   IMAGE   ...",
            success=True,
            start_time=1000.0,
            end_time=1000.5,
            latency=0.5,
            run_id="abc-123",
            sequence=0,
        )
        assert r.success
        assert r.docker_cli_args is not None
        assert r.docker_cli_args.command == "ps"

    def test_failed_record(self):
        r = ToolCallRecord(
            tool="remove_container",
            input_raw='{"container_id":"xyz"}',
            input_parsed={"container_id": "xyz"},
            success=False,
            error="Error: container not found",
            start_time=1000.0,
            end_time=1001.0,
            latency=1.0,
            run_id="def-456",
            sequence=1,
        )
        assert not r.success
        assert r.docker_cli_args is None


class TestTrajectoryMetrics:
    def test_defaults(self):
        m = TrajectoryMetrics()
        assert m.total_tool_calls == 0
        assert m.docker_commands_used == []
        assert not m.loop_detected


# ── collector tests ─────────────────────────────────────────────────


class TestTrajectoryCollector:
    def _make_run_id(self):
        return str(uuid.uuid4())

    def test_basic_tool_lifecycle(self):
        c = TrajectoryCollector()
        rid = self._make_run_id()

        c.on_tool_start(
            {"name": "docker_cli"},
            '{"command": "ps", "args": "-a"}',
            run_id=rid,
        )
        c.on_tool_end("CONTAINER ID   IMAGE   ...", run_id=rid)

        calls = c.tool_calls
        assert len(calls) == 1
        assert calls[0].tool == "docker_cli"
        assert calls[0].success
        assert calls[0].docker_cli_args is not None
        assert calls[0].docker_cli_args.command == "ps"
        assert calls[0].docker_cli_args.args == "-a"
        assert calls[0].docker_cli_args.full_command == "docker ps -a"
        assert calls[0].latency is not None
        assert calls[0].latency >= 0

    def test_docker_cli_compose_expansion(self):
        c = TrajectoryCollector()
        rid = self._make_run_id()

        c.on_tool_start(
            {"name": "docker_cli"},
            '{"command": "compose up", "args": "-d --build", "cwd": "/app"}',
            run_id=rid,
        )
        c.on_tool_end("Creating network ...", run_id=rid)

        calls = c.tool_calls
        assert calls[0].docker_cli_args.command == "compose up"
        assert calls[0].docker_cli_args.cwd == "/app"
        assert calls[0].docker_cli_args.full_command == "docker compose up -d --build"

    def test_non_docker_tool_no_expansion(self):
        c = TrajectoryCollector()
        rid = self._make_run_id()

        c.on_tool_start(
            {"name": "remove_container"},
            '{"container_id": "abc123"}',
            run_id=rid,
        )
        c.on_tool_end('{"success": true}', run_id=rid)

        calls = c.tool_calls
        assert calls[0].tool == "remove_container"
        assert calls[0].docker_cli_args is None
        assert calls[0].success

    def test_error_detection(self):
        c = TrajectoryCollector()
        rid = self._make_run_id()

        c.on_tool_start({"name": "docker_cli"}, '{"command": "run"}', run_id=rid)
        c.on_tool_end("Error (exit 1): port already in use", run_id=rid)

        calls = c.tool_calls
        assert not calls[0].success
        assert calls[0].error is not None

    def test_tool_exception(self):
        c = TrajectoryCollector()
        rid = self._make_run_id()

        c.on_tool_start({"name": "docker_cli"}, '{"command": "build"}', run_id=rid)
        c.on_tool_error(RuntimeError("Docker daemon not running"), run_id=rid)

        calls = c.tool_calls
        assert not calls[0].success
        assert "Docker daemon" in calls[0].error

    def test_sequence_ordering(self):
        c = TrajectoryCollector()

        for i in range(3):
            rid = self._make_run_id()
            c.on_tool_start({"name": f"tool_{i}"}, "{}", run_id=rid)
            c.on_tool_end("ok", run_id=rid)

        calls = c.tool_calls
        assert [tc.sequence for tc in calls] == [0, 1, 2]

    def test_loop_detection_same_tool(self):
        c = TrajectoryCollector(max_repeated_calls=3)

        for _ in range(4):
            rid = self._make_run_id()
            c.on_tool_start(
                {"name": "docker_cli"},
                '{"command": "ps"}',
                run_id=rid,
            )
            c.on_tool_end("CONTAINER ID ...", run_id=rid)

        assert c.loop_detected

    def test_loop_detection_empty_results(self):
        c = TrajectoryCollector(max_repeated_calls=3)

        for _ in range(3):
            rid = self._make_run_id()
            c.on_tool_start({"name": "docker_cli"}, '{"command": "ps"}', run_id=rid)
            c.on_tool_end("", run_id=rid)

        assert c.loop_detected

    def test_no_loop_with_varied_calls(self):
        c = TrajectoryCollector(max_repeated_calls=5)

        commands = ["ps", "images", "network ls", "volume ls", "info"]
        for cmd in commands:
            rid = self._make_run_id()
            c.on_tool_start(
                {"name": "docker_cli"},
                json.dumps({"command": cmd}),
                run_id=rid,
            )
            c.on_tool_end("some output", run_id=rid)

        assert not c.loop_detected

    def test_llm_tracking(self):
        c = TrajectoryCollector()
        rid = self._make_run_id()

        c.on_chat_model_start(
            {"name": "gpt-4o-mini"},
            [[{"role": "user", "content": "list containers"}]],
            run_id=rid,
        )

        # Simulate LLMResult
        class FakeLLMResult:
            llm_output = {"token_usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}

        c.on_llm_end(FakeLLMResult(), run_id=rid)

        llms = c.llm_calls
        assert len(llms) == 1
        assert llms[0].model == "gpt-4o-mini"
        assert llms[0].token_usage["total_tokens"] == 150

    def test_finalize_produces_complete_record(self):
        c = TrajectoryCollector()

        # Simulate a full turn
        rid1 = self._make_run_id()
        c.on_tool_start({"name": "docker_cli"}, '{"command": "ps", "args": "-a"}', run_id=rid1)
        c.on_tool_end("CONTAINER ID ...", run_id=rid1)

        rid2 = self._make_run_id()
        c.on_tool_start(
            {"name": "docker_cli"},
            '{"command": "run", "args": "-d -p 8080:80 nginx"}',
            run_id=rid2,
        )
        c.on_tool_end("abc123def456", run_id=rid2)

        record = c.finalize(task="run nginx on port 8080", thread_id="test-thread")

        assert isinstance(record, TrajectoryRecord)
        assert record.task == "run nginx on port 8080"
        assert record.thread_id == "test-thread"
        assert len(record.tool_calls) == 2
        assert record.metrics.total_tool_calls == 2
        assert record.metrics.successful_tool_calls == 2
        assert record.metrics.failed_tool_calls == 0
        assert record.metrics.docker_commands_used == ["ps", "run"]
        assert record.success
        assert record.completed_at is not None

    def test_clear_resets_state(self):
        c = TrajectoryCollector()

        rid = self._make_run_id()
        c.on_tool_start({"name": "docker_cli"}, '{"command": "ps"}', run_id=rid)
        c.on_tool_end("output", run_id=rid)
        assert len(c.tool_calls) == 1

        c.clear()
        assert len(c.tool_calls) == 0
        assert not c.loop_detected

    def test_orphaned_end_is_ignored(self):
        c = TrajectoryCollector()
        c.on_tool_end("orphan output", run_id=self._make_run_id())
        # Should not crash, just log warning
        assert len(c.tool_calls) == 0

    def test_parse_input_non_json(self):
        c = TrajectoryCollector()
        rid = self._make_run_id()

        c.on_tool_start({"name": "docker_cli"}, "not json at all", run_id=rid)
        c.on_tool_end("ok", run_id=rid)

        calls = c.tool_calls
        assert calls[0].input_parsed == {"raw": "not json at all"}
        assert calls[0].docker_cli_args is None  # can't expand without "command" key

    def test_parse_input_python_repr(self):
        """LangChain sends Python repr dicts (single-quoted), not JSON."""
        c = TrajectoryCollector()
        rid = self._make_run_id()

        c.on_tool_start(
            {"name": "docker_cli"},
            "{'command': 'network ls'}",
            run_id=rid,
        )
        c.on_tool_end("NETWORK ID ...", run_id=rid)

        calls = c.tool_calls
        assert calls[0].input_parsed == {"command": "network ls"}
        assert calls[0].docker_cli_args is not None
        assert calls[0].docker_cli_args.command == "network ls"
        assert calls[0].docker_cli_args.full_command == "docker network ls"

    def test_parse_input_python_repr_with_args(self):
        c = TrajectoryCollector()
        rid = self._make_run_id()

        c.on_tool_start(
            {"name": "docker_cli"},
            "{'command': 'run', 'args': '-d -p 8080:80 nginx', 'cwd': '/app'}",
            run_id=rid,
        )
        c.on_tool_end("abc123", run_id=rid)

        calls = c.tool_calls
        assert calls[0].docker_cli_args.command == "run"
        assert calls[0].docker_cli_args.args == "-d -p 8080:80 nginx"
        assert calls[0].docker_cli_args.cwd == "/app"
        assert calls[0].docker_cli_args.full_command == "docker run -d -p 8080:80 nginx"


# ── timestamp tests ─────────────────────────────────────────────────


class TestTimestampOrdering:
    def _make_run_id(self):
        return str(uuid.uuid4())

    def test_started_at_before_completed_at(self):
        """Bug fix: completed_at must be >= started_at."""
        c = TrajectoryCollector()
        rid = self._make_run_id()

        c.on_tool_start({"name": "docker_cli"}, '{"command": "ps"}', run_id=rid)
        time.sleep(0.01)  # ensure measurable gap
        c.on_tool_end("CONTAINER ID ...", run_id=rid)

        record = c.finalize(task="test timestamps")
        assert record.started_at <= record.completed_at

    def test_started_at_captured_at_first_tool(self):
        """started_at should reflect when the first tool was called, not finalize time."""
        c = TrajectoryCollector()

        before = time.time()
        rid = self._make_run_id()
        c.on_tool_start({"name": "docker_cli"}, '{"command": "ps"}', run_id=rid)
        c.on_tool_end("ok", run_id=rid)

        time.sleep(0.05)  # significant gap before finalize
        record = c.finalize(task="test")

        # started_at should be close to 'before', not close to finalize
        started_ts = record.started_at.timestamp()
        completed_ts = record.completed_at.timestamp()
        assert started_ts < completed_ts
        assert started_ts - before < 0.1  # started_at within 100ms of first tool


# ── redaction tests ─────────────────────────────────────────────────


class TestCredentialRedaction:
    def test_postgres_password_redacted(self):
        c = TrajectoryCollector()
        result = c._redact_string("POSTGRES_PASSWORD=secretpass123")
        assert result == "POSTGRES_PASSWORD=[REDACTED]"
        assert "secretpass123" not in result

    def test_generic_password_redacted(self):
        c = TrajectoryCollector()
        result = c._redact_string("password=hunter2")
        assert "hunter2" not in result
        assert "[REDACTED]" in result

    def test_api_key_redacted(self):
        c = TrajectoryCollector()
        result = c._redact_string("api_key=sk-1234567890abcdef")
        assert "sk-1234567890" not in result

    def test_non_secret_not_redacted(self):
        c = TrajectoryCollector()
        assert c._redact_string("POSTGRES_DB=cicd") == "POSTGRES_DB=cicd"
        assert c._redact_string("POSTGRES_USER=admin") == "POSTGRES_USER=admin"
        assert c._redact_string("no credentials here") == "no credentials here"

    def test_multiple_secrets_in_line(self):
        c = TrajectoryCollector()
        result = c._redact_string("SECRET_KEY=abc123def token=xyz789")
        assert "abc123def" not in result
        assert "xyz789" not in result
        assert result.count("[REDACTED]") == 2

    def test_finalize_redacts_task(self):
        c = TrajectoryCollector()
        rid = str(uuid.uuid4())
        c.on_tool_start({"name": "docker_cli"}, '{"command": "ps"}', run_id=rid)
        c.on_tool_end("ok", run_id=rid)

        record = c.finalize(
            task="Run postgres with POSTGRES_PASSWORD=secretpass123"
        )
        assert "secretpass123" not in record.task
        assert "[REDACTED]" in record.task

    def test_redact_disabled(self):
        c = TrajectoryCollector(redact=False)
        rid = str(uuid.uuid4())
        c.on_tool_start({"name": "docker_cli"}, '{"command": "ps"}', run_id=rid)
        c.on_tool_end("ok", run_id=rid)

        record = c.finalize(
            task="POSTGRES_PASSWORD=secretpass123"
        )
        assert "secretpass123" in record.task


# ── docker_commands_used tests ──────────────────────────────────────


class TestDockerCommandsUsed:
    def _make_run_id(self):
        return str(uuid.uuid4())

    def test_commands_collected_from_python_repr_input(self):
        """Bug fix: docker_commands_used must work with Python repr input strings."""
        c = TrajectoryCollector()

        commands = ["network ls", "volume ls", "ps", "run", "network create"]
        for cmd in commands:
            rid = self._make_run_id()
            c.on_tool_start(
                {"name": "docker_cli"},
                f"{{'command': '{cmd}'}}",
                run_id=rid,
            )
            c.on_tool_end("ok", run_id=rid)

        record = c.finalize(task="test commands")
        assert record.metrics.docker_commands_used == commands

    def test_commands_deduplicated(self):
        c = TrajectoryCollector()

        for _ in range(3):
            rid = self._make_run_id()
            c.on_tool_start(
                {"name": "docker_cli"},
                "{'command': 'ps'}",
                run_id=rid,
            )
            c.on_tool_end("ok", run_id=rid)

        record = c.finalize(task="test dedup")
        assert record.metrics.docker_commands_used == ["ps"]

    def test_loop_detected_does_not_override_success(self):
        """Bug fix: loop_detected should be informational, not force success=False."""
        c = TrajectoryCollector(max_repeated_calls=3)

        # Trigger loop detection
        for _ in range(4):
            rid = self._make_run_id()
            c.on_tool_start(
                {"name": "docker_cli"},
                '{"command": "ps"}',
                run_id=rid,
            )
            c.on_tool_end("CONTAINER ID ...", run_id=rid)

        assert c.loop_detected

        # Finalize with success=True (caller says it succeeded)
        record = c.finalize(task="test", success=True)
        assert record.success is True
        assert record.metrics.loop_detected is True
        assert record.error is None


class TestToolCallRedaction:
    def _make_run_id(self):
        return str(uuid.uuid4())

    def test_credentials_redacted_in_docker_cli_args(self):
        """Bug fix: POSTGRES_PASSWORD must not appear in serialized tool calls."""
        c = TrajectoryCollector()
        rid = self._make_run_id()

        input_str = (
            "{'command': 'run', 'args': '-d -e POSTGRES_PASSWORD=secretpass123 postgres'}"
        )
        c.on_tool_start({"name": "docker_cli"}, input_str, run_id=rid)
        c.on_tool_end("abc123", run_id=rid)

        record = c.finalize(task="run postgres with POSTGRES_PASSWORD=secretpass123")

        # Task redacted
        assert "secretpass123" not in record.task

        # Tool call fields redacted
        tc = record.tool_calls[0]
        assert "secretpass123" not in tc.input_raw
        assert "secretpass123" not in str(tc.input_parsed)
        assert "secretpass123" not in tc.docker_cli_args.args
        assert "secretpass123" not in tc.docker_cli_args.full_command
        assert "[REDACTED]" in tc.input_raw
        assert "[REDACTED]" in tc.docker_cli_args.full_command

    def test_output_redacted(self):
        c = TrajectoryCollector()
        rid = self._make_run_id()

        c.on_tool_start({"name": "docker_cli"}, '{"command": "inspect"}', run_id=rid)
        c.on_tool_end("POSTGRES_PASSWORD=hunter2 in environment", run_id=rid)

        record = c.finalize(task="inspect")
        tc = record.tool_calls[0]
        assert "hunter2" not in tc.output
        assert "[REDACTED]" in tc.output

    def test_non_secret_args_preserved(self):
        c = TrajectoryCollector()
        rid = self._make_run_id()

        c.on_tool_start(
            {"name": "docker_cli"},
            "{'command': 'run', 'args': '-d -p 8080:80 nginx'}",
            run_id=rid,
        )
        c.on_tool_end("abc123", run_id=rid)

        record = c.finalize(task="run nginx")
        tc = record.tool_calls[0]
        assert "-d -p 8080:80 nginx" in tc.docker_cli_args.args
        assert "[REDACTED]" not in tc.input_raw

    def test_redaction_disabled(self):
        c = TrajectoryCollector(redact=False)
        rid = self._make_run_id()

        c.on_tool_start(
            {"name": "docker_cli"},
            "{'command': 'run', 'args': '-e POSTGRES_PASSWORD=secret123 pg'}",
            run_id=rid,
        )
        c.on_tool_end("ok", run_id=rid)

        record = c.finalize(task="POSTGRES_PASSWORD=secret123")
        assert "secret123" in record.task
        assert "secret123" in record.tool_calls[0].input_raw


# ── summarizer tests ────────────────────────────────────────────────


class TestSummarizeTrajectory:
    def test_basic_summary(self):
        record = TrajectoryRecord(
            task="run nginx",
            tool_calls=[
                ToolCallRecord(
                    tool="docker_cli",
                    input_raw="{}",
                    input_parsed={"command": "ps"},
                    docker_cli_args=DockerCliArgs(
                        command="ps", full_command="docker ps"
                    ),
                    success=True,
                    start_time=0,
                    end_time=0.5,
                    latency=0.5,
                    run_id="a",
                    sequence=0,
                ),
                ToolCallRecord(
                    tool="docker_cli",
                    input_raw="{}",
                    input_parsed={"command": "run", "args": "-d nginx"},
                    docker_cli_args=DockerCliArgs(
                        command="run",
                        args="-d nginx",
                        full_command="docker run -d nginx",
                    ),
                    success=True,
                    start_time=1,
                    end_time=2,
                    latency=1.0,
                    run_id="b",
                    sequence=1,
                ),
            ],
            metrics=TrajectoryMetrics(
                total_tool_calls=2,
                successful_tool_calls=2,
                total_tokens=500,
                docker_commands_used=["ps", "run"],
            ),
        )

        summary = summarize_trajectory(record)
        assert "run nginx" in summary
        assert "docker ps" in summary
        assert "docker run -d nginx" in summary
        assert "success" in summary
        assert "tokens=500" in summary

    def test_failed_summary(self):
        record = TrajectoryRecord(
            task="build app",
            tool_calls=[
                ToolCallRecord(
                    tool="docker_cli",
                    input_raw="{}",
                    input_parsed={},
                    success=False,
                    error="Error: Dockerfile not found",
                    start_time=0,
                    end_time=1,
                    latency=1.0,
                    run_id="c",
                    sequence=0,
                ),
            ],
            metrics=TrajectoryMetrics(
                total_tool_calls=1,
                failed_tool_calls=1,
            ),
        )
        summary = summarize_trajectory(record)
        assert "failed" in summary

    def test_truncation(self):
        record = TrajectoryRecord(
            task="x" * 900,
            metrics=TrajectoryMetrics(),
        )
        summary = summarize_trajectory(record)
        assert len(summary) <= 800


class TestTrajectoryToDict:
    def test_serialization(self):
        record = TrajectoryRecord(
            task="test",
            metrics=TrajectoryMetrics(total_tool_calls=1),
        )
        d = trajectory_to_dict(record)
        assert isinstance(d, dict)
        assert d["task"] == "test"
        assert d["metrics"]["total_tool_calls"] == 1
        # Should be JSON-serializable
        json.dumps(d, default=str)
