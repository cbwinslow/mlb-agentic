from __future__ import annotations

import json
from pathlib import Path

import typer

from .runtime import run_bootstrap

app = typer.Typer(help="MLB agent bootstrap runtime")


@app.command()
def run(
    request_file: str = typer.Argument(..., help="Path to JSON request file"),
    root_dir: str = typer.Option(".", help="Root directory of bootstrap pack"),
):
    request = json.loads(Path(request_file).read_text(encoding="utf-8"))
    result = run_bootstrap(root_dir=root_dir, request_data=request)
    typer.echo(result.model_dump_json(indent=2))
    if result.status != "success":
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
