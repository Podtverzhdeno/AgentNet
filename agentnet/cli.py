"""AgentNet command-line interface.

Subcommands mirror the documented CLI in ``docs/modules/cli.md``. Phase 2.C
adds optional persistence: pass ``--persist`` (or ``AGENTNET_CHECKPOINTER``)
and every node transition is stored in SQLite, enabling ``session list``
and ``session get`` to inspect past runs.
"""

from __future__ import annotations

import json
import os

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .graph import build_graph, get_session_state, run_session
from .mcp_gateway import MCPGateway, load_config
from .persistence import default_checkpoint_uri, list_thread_ids, make_checkpointer
from .state import SessionRequest

app = typer.Typer(no_args_is_help=True, add_completion=False, help="AgentNet CLI")
session_app = typer.Typer(help="Manage AgentNet sessions")
app.add_typer(session_app, name="session")
mcp_app = typer.Typer(help="Inspect and exercise the MCP gateway")
app.add_typer(mcp_app, name="mcp")

console = Console()


def _resolve_persist(option: str | None) -> str | None:
    """Resolve a persistence URI from a CLI flag or environment variable.

    Empty strings and the literal ``"none"`` mean "no persistence".
    """

    if option is None:
        option = os.environ.get("AGENTNET_CHECKPOINTER")
    if option in (None, "", "none", "off", "false"):
        return None
    return option


@session_app.command("start")
def session_start(
    task: str = typer.Argument(..., help="Idea or task description"),
    mode: str = typer.Option("auto", help="auto | confirm-each-step | manual"),
    max_iterations: int = typer.Option(3, help="Maximum reflection iterations"),
    score_threshold: float = typer.Option(0.8, help="Score required to terminate"),
    thread_id: str | None = typer.Option(None, "--thread-id", help="Reuse a specific thread id"),
    persist: str | None = typer.Option(
        None,
        "--persist",
        help=(
            "Checkpointer URI (memory | sqlite::memory: | sqlite:///path.db). "
            "Default: AGENTNET_CHECKPOINTER env or no persistence."
        ),
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON instead of pretty output"),
) -> None:
    """Run a session locally and print its final state."""

    request = SessionRequest(
        task=task,
        mode=mode,  # type: ignore[arg-type]
        max_iterations=max_iterations,
        score_threshold=score_threshold,
    )
    result = run_session(
        request,
        thread_id=thread_id,
        checkpointer_uri=_resolve_persist(persist),
    )
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


@session_app.command("list")
def session_list(
    persist: str | None = typer.Option(
        None,
        "--persist",
        help="Checkpointer URI. Defaults to AGENTNET_CHECKPOINTER or the on-disk default.",
    ),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List sessions stored in the checkpointer."""

    uri = _resolve_persist(persist) or default_checkpoint_uri()
    checkpointer = make_checkpointer(uri)
    threads = list_thread_ids(checkpointer)
    if json_output:
        typer.echo(json.dumps({"checkpointer": uri, "threads": threads}, indent=2))
        return
    table = Table(title=f"Sessions ({uri})")
    table.add_column("thread_id", overflow="fold")
    for tid in threads:
        table.add_row(tid)
    console.print(table)


@session_app.command("get")
def session_get(
    thread_id: str = typer.Argument(..., help="Session / thread id"),
    persist: str | None = typer.Option(
        None,
        "--persist",
        help="Checkpointer URI. Defaults to AGENTNET_CHECKPOINTER or the on-disk default.",
    ),
) -> None:
    """Print the latest persisted state for a session."""

    uri = _resolve_persist(persist) or default_checkpoint_uri()
    checkpointer = make_checkpointer(uri)
    state = get_session_state(thread_id, checkpointer)
    if state is None:
        typer.echo(json.dumps({"error": f"no checkpoint for {thread_id}"}))
        raise typer.Exit(code=1)
    typer.echo(json.dumps(state, indent=2, default=str, ensure_ascii=False))


@mcp_app.command("validate")
def mcp_validate(
    config: str = typer.Argument(..., help="Path to gateway YAML config"),
) -> None:
    """Load and validate a gateway YAML config, summarising what it permits."""

    cfg = load_config(config)
    table = Table(title=f"Gateway ({config})")
    table.add_column("section")
    table.add_column("count", justify="right")
    table.add_row("backends", str(len(cfg.backends)))
    table.add_row("tools", str(len(cfg.tools)))
    table.add_row("roles", str(len(cfg.roles)))
    console.print(table)
    for role, rcfg in cfg.roles.items():
        console.print(f"[bold]{role}[/bold] allow={rcfg.allow!r} approval={rcfg.approval!r}")


@mcp_app.command("tools")
def mcp_tools(
    role: str = typer.Argument(..., help="Role to query"),
    config: str = typer.Option(..., "--config", help="Path to gateway YAML config"),
) -> None:
    """Print the tools accessible to *role* under *config*."""

    gateway = MCPGateway.from_config(config)
    tools = gateway.list_tools(role)
    typer.echo(json.dumps({"role": role, "tools": tools}, indent=2))


@mcp_app.command("call")
def mcp_call(
    tool: str = typer.Argument(..., help="Tool name"),
    role: str = typer.Option(..., "--role", help="Calling role"),
    config: str = typer.Option(..., "--config", help="Path to gateway YAML config"),
    params: str = typer.Option("{}", "--params", help="JSON-encoded params"),
    approve: bool = typer.Option(False, "--approve", help="Pass approval_decision='approve'"),
) -> None:
    """Invoke a tool through the gateway (HTTP transports require a live server)."""

    gateway = MCPGateway.from_config(config)
    parsed: dict[str, object] = json.loads(params or "{}")
    result = gateway.call(
        role=role,
        tool=tool,
        params=parsed,
        approval_decision="approve" if approve else None,
    )
    typer.echo(json.dumps({"result": result}, indent=2, default=str, ensure_ascii=False))


@app.command("version")
def version() -> None:
    from . import __version__

    typer.echo(__version__)


@app.command("graph")
def show_graph() -> None:
    """Print a human-readable description of the compiled graph."""

    graph = build_graph()
    nodes = list(graph.get_graph().nodes)
    edges = list(graph.get_graph().edges)
    typer.echo(json.dumps({"nodes": nodes, "edges": [str(e) for e in edges]}, indent=2))


if __name__ == "__main__":
    app()
