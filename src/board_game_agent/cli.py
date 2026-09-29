from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from board_game_agent.config import Settings
from board_game_agent.llm.client import LLMClient
from board_game_agent.orchestrator import Orchestrator
from board_game_agent.session.store import SessionStore

app = typer.Typer(help="Board game advisor CLI — full-game Session, NL in / NL out.", no_args_is_help=True)


def _orch(verbose: bool = False) -> Orchestrator:
    settings = Settings()
    if not settings.deepseek_api_key and verbose:
        typer.echo("警告: 未设置 DEEPSEEK_API_KEY", err=True)
    return Orchestrator(settings, LLMClient(settings), SessionStore(settings.sessions_dir))


def _sid(use: Optional[str]) -> Optional[str]:
    return use


@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", help="打印更多调试信息"),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@app.command("new")
def cmd_new(
    ctx: typer.Context,
    name: str = typer.Option("", "--name", help="对局名称"),
) -> None:
    orch = _orch(ctx.obj.get("verbose", False))
    sid = orch.new_session(name=name)
    typer.echo(f"已创建 Session: {sid}")


@app.command("use")
def cmd_use(sid: str) -> None:
    settings = Settings()
    store = SessionStore(settings.sessions_dir)
    if not (store.path(sid) / "meta.json").exists():
        raise typer.BadParameter(f"Session 不存在: {sid}")
    store.set_current(sid)
    typer.echo(f"当前 Session: {sid}")


@app.command("rules")
def cmd_rules(ctx: typer.Context, path: Path) -> None:
    if not path.exists():
        raise typer.BadParameter(f"文件不存在: {path}")
    orch = _orch(ctx.obj.get("verbose", False))
    typer.echo(orch.load_rules(None, path))


@app.command("say")
def cmd_say(ctx: typer.Context, text: str) -> None:
    orch = _orch(ctx.obj.get("verbose", False))
    typer.echo(orch.say(None, text))


@app.command("advise")
def cmd_advise(ctx: typer.Context) -> None:
    orch = _orch(ctx.obj.get("verbose", False))
    typer.echo(orch.advise(None))


@app.command("ask")
def cmd_ask(ctx: typer.Context, text: str) -> None:
    orch = _orch(ctx.obj.get("verbose", False))
    typer.echo(orch.ask(None, text))


@app.command("status")
def cmd_status(ctx: typer.Context) -> None:
    orch = _orch(ctx.obj.get("verbose", False))
    typer.echo(orch.status(None))


@app.command("undo")
def cmd_undo(ctx: typer.Context) -> None:
    orch = _orch(ctx.obj.get("verbose", False))
    typer.echo(orch.undo(None))


@app.command("end")
def cmd_end(ctx: typer.Context) -> None:
    orch = _orch(ctx.obj.get("verbose", False))
    typer.echo(orch.end(None))
