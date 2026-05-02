"""AgentNet command-line interface.

Subcommands mirror the documented CLI in ``docs/modules/cli.md`` but only
the local-execution flavours are implemented in Phase 1. Anything that
talks to a remote orchestrator service will be wired up later.
"""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.panel import Panel

from .graph import run_session
from .state import SessionRequest

app = typer.Typer(no_args_is_help=True, add_completion=False, help="AgentNet CLI")
session_app = typer.Typer(help="Manage AgentNet sessions")
app.add_typer(session_app, name="session")

console = Console()


@session_app.command("start")
def session_start(
    task: str = typer.Argument(..., help="Idea or task description"),
    mode: str = typer.Option("auto", help="auto | confirm-each-step | manual"),
    max_iterations: int = typer.Option(3, help="Maximum reflection iterations"),
    score_threshold: float = typer.Option(0.8, help="Score required to terminate"),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON instead of pretty output"),
) -> None:
    """Run a session locally and print its final state."""

    request = SessionRequest(
        task=task,
        mode=mode,  # type: ignore[arg-type]
        max_iterations=max_iterations,
        score_threshold=score_threshold,
    )
    result = run_session(request)
    if json_output:
        typer.echo(result.model_dump_json(indent=2))
        return
    console.print(
        Panel.fit(
            f"[bold]Session[/bold] {result.session_id}\n"
            f"Iterations: {result.iterations}\n"
            f"Score: {result.score}\n"
            f"Feedback: {result.feedback}",
            title="AgentNet",
        )
    )
    if result.result is not None:
        console.print_json(
            data=result.result if isinstance(result.result, dict) else {"text": result.result}
        )


@app.command("version")
def version() -> None:
    from . import __version__

    typer.echo(__version__)


@app.command("graph")
def show_graph() -> None:
    """Print a human-readable description of the compiled graph."""

    from .graph import build_graph

    graph = build_graph()
    nodes = list(graph.get_graph().nodes)
    edges = list(graph.get_graph().edges)
    typer.echo(json.dumps({"nodes": nodes, "edges": [str(e) for e in edges]}, indent=2))


if __name__ == "__main__":
    app()
