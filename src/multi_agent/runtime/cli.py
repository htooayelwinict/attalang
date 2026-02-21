import uuid

import click

from src.multi_agent.runtime import create_docker_graph_runtime


@click.command()
@click.option("--model", default=None, help="OpenRouter model name")
@click.option("--temperature", default=0.0, type=float, show_default=True)
@click.option("--thread-id", default=None, help="Conversation thread id")
@click.option("--prompt", default=None, help="Single-shot prompt")
@click.option("--hitl/--no-hitl", default=False, help="Enable human-in-the-loop for dangerous tools")
def main(
    model: str | None,
    temperature: float,
    thread_id: str | None,
    prompt: str | None,
    hitl: bool,
) -> None:
    runtime = create_docker_graph_runtime(
        model=model,
        temperature=temperature,
        enable_hitl=hitl,
    )
    active_thread = thread_id or str(uuid.uuid4())

    if hitl:
        click.echo("Docker agent ready (HITL enabled for dangerous operations).")
    else:
        click.echo("Docker agent ready.")

    click.echo("Type 'exit' or 'quit' to stop.\n")

    if prompt:
        response = runtime.run_turn(prompt, thread_id=active_thread)
        click.echo(response)
        return

    while True:
        try:
            user_input = click.prompt("docker")
        except (EOFError, KeyboardInterrupt):
            click.echo()
            break

        if user_input.strip().lower() in {"exit", "quit"}:
            break

        response = runtime.run_turn(user_input, thread_id=active_thread)
        click.echo(response)


if __name__ == "__main__":
    main()
