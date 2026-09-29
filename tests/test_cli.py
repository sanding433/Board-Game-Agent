from pathlib import Path

from typer.testing import CliRunner

from board_game_agent.cli import app

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "new" in result.stdout


def test_new_and_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SESSIONS_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test")
    result = runner.invoke(app, ["new", "--name", "cli-toy"])
    assert result.exit_code == 0
    assert "Session" in result.stdout
    status = runner.invoke(app, ["status"])
    assert status.exit_code == 0
