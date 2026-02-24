"""CLI for the Programmatic Docker Agent (V3).

Usage:
    .venv/bin/python -m src.multi_agent_v3.runtime.cli_v3
    .venv/bin/python -m src.multi_agent_v3.runtime.cli_v3 --prompt "deploy nginx with redis"
    multi-agent-cli-v3 -v --prompt "set up a CI/CD pipeline"
"""

import json
import logging
import uuid
from pathlib import Path

import click

from src.multi_agent_v3.runtime import create_programmatic_runtime
from src.multi_agent.runtime.verbose_callback import VerboseCallback
from src.multi_agent.trajectory import TrajectoryCollector, summarize_trajectory
from src.multi_agent.trajectory.summary import trajectory_to_dict


@click.command()
@click.option("--model", default=None, help="OpenRouter model name")
@click.option("--temperature", default=0.0, type=float, show_default=True)
@click.option("--thread-id", default=None, help="Conversation thread id")
@click.option("--prompt", default=None, help="Single-shot prompt")
@click.option(
    "--provider-sort",
    default=None,
    type=click.Choice(["latency", "throughput", "price"], case_sensitive=False),
    help="OpenRouter provider sorting strategy",
)
@click.option("--debug/--no-debug", default=False, help="Enable debug logging")
@click.option("-v", "--verbose", is_flag=True, help="Show real-time tool calls and LLM activity")
@click.option("--trajectory/--no-trajectory", default=True, help="Collect tool call trajectories")
@click.option("--trajectory-dir", default=None, type=click.Path(), help="Trajectory log directory")
def main(
    model: str | None,
    temperature: float,
    thread_id: str | None,
    prompt: str | None,
    provider_sort: str | None,
    debug: bool,
    verbose: bool,
    trajectory: bool,
    trajectory_dir: str | None,
) -> None:
    if debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    runtime = create_programmatic_runtime(
        model=model,
        temperature=temperature,
        provider_sort=provider_sort,
    )
    active_thread = thread_id or str(uuid.uuid4())

    verbose_callback = VerboseCallback() if verbose else None

    traj_collector = TrajectoryCollector() if trajectory else None
    traj_log_dir = Path(trajectory_dir) if trajectory_dir else Path(".trajectories")
    if traj_collector:
        traj_log_dir.mkdir(parents=True, exist_ok=True)

    def _build_callbacks() -> list | None:
        cbs = []
        if verbose_callback:
            cbs.append(verbose_callback)
        if traj_collector:
            traj_collector.clear()
            cbs.append(traj_collector)
        return cbs or None

    def _finalize_trajectory(task: str) -> None:
        if not traj_collector:
            return
        record = traj_collector.finalize(task=task, thread_id=active_thread)
        summary = summarize_trajectory(record)
        m = record.metrics
        click.secho(
            f"\n📊 Trajectory: {m.total_tool_calls} tools "
            f"({m.successful_tool_calls}✓ {m.failed_tool_calls}✗) "
            f"| {m.total_llm_calls} LLM calls "
            f"| {m.total_tokens} tokens "
            f"| {m.total_latency:.1f}s total",
            fg="blue",
            dim=True,
        )
        if m.loop_detected:
            click.secho("⚠️  Loop detected in trajectory", fg="yellow")

        log_file = traj_log_dir / f"trajectory_{active_thread}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(trajectory_to_dict(record), default=str) + "\n")

    click.secho("⚡ Programmatic Docker Agent (V3) ready.", fg="green", bold=True)
    click.secho(
        "  Mode: code execution (writes Python that calls Docker tools directly)",
        fg="green",
        dim=True,
    )
    if trajectory:
        click.secho(f"  Trajectory: ON (logs → {traj_log_dir}/)", fg="blue", dim=True)
    click.echo("Type 'exit' or 'quit' to stop.\n")

    if prompt:
        callbacks = _build_callbacks()
        response = runtime.run_turn(prompt, thread_id=active_thread, callbacks=callbacks)
        click.echo(response)
        _finalize_trajectory(prompt)
        return

    while True:
        try:
            user_input = click.prompt("docker-prog")
        except (EOFError, KeyboardInterrupt):
            click.echo()
            break

        if user_input.strip().lower() in {"exit", "quit"}:
            break

        callbacks = _build_callbacks()
        response = runtime.run_turn(user_input, thread_id=active_thread, callbacks=callbacks)
        click.echo(response)
        _finalize_trajectory(user_input)


if __name__ == "__main__":
    main()
