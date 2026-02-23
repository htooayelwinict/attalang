import logging
import uuid

import click

from src.multi_agent.runtime import create_docker_graph_runtime
from src.multi_agent.runtime.verbose_callback import VerboseCallback


@click.command()
@click.option("--model", default=None, help="OpenRouter model name")
@click.option("--temperature", default=0.0, type=float, show_default=True)
@click.option("--thread-id", default=None, help="Conversation thread id")
@click.option("--prompt", default=None, help="Single-shot prompt")
@click.option("--hitl/--no-hitl", default=False, help="Enable human-in-the-loop for dangerous tools")
@click.option("--provider-sort", default=None, type=click.Choice(["latency", "throughput", "price"], case_sensitive=False), help="OpenRouter provider sorting strategy")
@click.option("--debug/--no-debug", default=False, help="Enable debug logging for trajectory loop detection")
@click.option("-v", "--verbose", is_flag=True, help="Show real-time tool calls and LLM activity")
def main(
    model: str | None,
    temperature: float,
    thread_id: str | None,
    prompt: str | None,
    hitl: bool,
    provider_sort: str | None,
    debug: bool,
    verbose: bool,
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

    if hitl:
        click.echo("Docker agent ready (HITL enabled for dangerous operations).")
    else:
        click.echo("Docker agent ready.")

    click.echo("Type 'exit' or 'quit' to stop.\n")

    if prompt:
        callbacks = [verbose_callback] if verbose_callback else None
        response = runtime.run_turn(prompt, thread_id=active_thread, callbacks=callbacks)
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

        callbacks = [verbose_callback] if verbose_callback else None
        response = runtime.run_turn(user_input, thread_id=active_thread, callbacks=callbacks)
        click.echo(response)


if __name__ == "__main__":
    main()
