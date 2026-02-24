import json
import logging
import uuid
from pathlib import Path

import click

from src.multi_agent.runtime import create_docker_graph_runtime
from src.multi_agent.runtime.verbose_callback import VerboseCallback
from src.multi_agent.trajectory import TrajectoryCollector, summarize_trajectory
from src.multi_agent.trajectory.summary import trajectory_to_dict


@click.command()
@click.option("--model", default=None, help="OpenRouter model name")
@click.option("--temperature", default=0.0, type=float, show_default=True)
@click.option("--thread-id", default=None, help="Conversation thread id")
@click.option("--prompt", default=None, help="Single-shot prompt")
@click.option("--hitl/--no-hitl", default=False, help="Enable human-in-the-loop for dangerous tools")
@click.option("--provider-sort", default=None, type=click.Choice(["latency", "throughput", "price"], case_sensitive=False), help="OpenRouter provider sorting strategy")
@click.option("--debug/--no-debug", default=False, help="Enable debug logging for trajectory loop detection")
@click.option("-v", "--verbose", is_flag=True, help="Show real-time tool calls and LLM activity")
@click.option("--trajectory/--no-trajectory", default=True, help="Collect tool call trajectories (default: on)")
@click.option("--trajectory-dir", default=None, type=click.Path(), help="Directory for trajectory JSONL logs")
def main(
    model: str | None,
    temperature: float,
    thread_id: str | None,
    prompt: str | None,
    hitl: bool,
    provider_sort: str | None,
    debug: bool,
    verbose: bool,
    trajectory: bool,
    trajectory_dir: str | None,
) -> None:
    # Configure debug logging
    if debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        # Enable verbose trajectory callback logging
        logging.getLogger("src.multi_agent.runtime.docker_trajectory").setLevel(logging.DEBUG)

    runtime = create_docker_graph_runtime(
        model=model,
        temperature=temperature,
        enable_hitl=hitl,
        provider_sort=provider_sort,
    )
    active_thread = thread_id or str(uuid.uuid4())

    # Set up verbose callback if requested
    verbose_callback = VerboseCallback() if verbose else None

    # Set up trajectory collector
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
        # Log summary
        summary = summarize_trajectory(record)
        m = record.metrics
        click.secho(
            f"\n📊 Trajectory: {m.total_tool_calls} tools "
            f"({m.successful_tool_calls}✓ {m.failed_tool_calls}✗) "
            f"| {m.total_llm_calls} LLM calls "
            f"| {m.total_tokens} tokens "
            f"| {m.total_latency:.1f}s total",
            fg="blue", dim=True,
        )
        if m.loop_detected:
            click.secho("⚠️  Loop detected in trajectory", fg="yellow")
        if m.docker_commands_used:
            click.secho(
                f"   Docker commands: {', '.join(m.docker_commands_used)}",
                fg="blue", dim=True,
            )
        # Persist to JSONL
        log_file = traj_log_dir / f"trajectory_{active_thread}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(trajectory_to_dict(record), default=str) + "\n")

    if hitl:
        click.echo("Docker agent ready (HITL enabled for dangerous operations).")
    else:
        click.echo("Docker agent ready.")

    if trajectory:
        click.secho(f"Trajectory collection: ON (logs → {traj_log_dir}/)", fg="blue", dim=True)

    click.echo("Type 'exit' or 'quit' to stop.\n")

    if prompt:
        callbacks = _build_callbacks()
        response = runtime.run_turn(prompt, thread_id=active_thread, callbacks=callbacks)
        click.echo(response)
        _finalize_trajectory(prompt)
        return

    while True:
        try:
            user_input = click.prompt("docker")
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
