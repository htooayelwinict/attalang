import sys
import uuid

import click

from src.multi_agent_v2.runtime import create_docker_runtime_v2


@click.command()
@click.option("--model", default=None, help="Model name")
@click.option("--temperature", default=0.0, type=float, show_default=True)
@click.option("--thread-id", default=None, help="Conversation thread id")
@click.option("--prompt", default=None, help="Single-shot prompt")
@click.option("-v", "--verbose", is_flag=True, help="Show detailed tool calls")
def main(
    model: str | None,
    temperature: float,
    thread_id: str | None,
    prompt: str | None,
    verbose: bool,
) -> None:
    runtime = create_docker_runtime_v2(model=model, temperature=temperature)
    active_thread = thread_id or str(uuid.uuid4())

    if prompt:
        if verbose:
            for event in runtime.run_turn_verbose(prompt, thread_id=active_thread):
                click.echo(event)
        else:
            click.echo(runtime.run_turn(prompt, thread_id=active_thread))
        return

    mode = "verbose" if verbose else "normal"
    click.echo(f"Docker v2 agent ready ({mode} mode). Type 'exit' or 'quit' to stop.")

    while True:
        try:
            user_input = click.prompt("docker-v2")
        except (EOFError, KeyboardInterrupt):
            click.echo()
            break

        if user_input.strip().lower() in {"exit", "quit"}:
            break

        if verbose:
            for event in runtime.run_turn_verbose(user_input, thread_id=active_thread):
                click.echo(event)
        else:
            response = runtime.run_turn(user_input, thread_id=active_thread)
            click.echo(response)


if __name__ == "__main__":
    main()
