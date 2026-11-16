import os
from pathlib import Path

import pytest

from mini_amc import cli


def test_help_lists_subcommands(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for cmd in ("generate", "omr", "grades", "web"):
        assert cmd in out


def test_subcommand_routing(monkeypatch):
    calls = {}
    cases = (
        ("generate", "mini_amc.gen.generate"),
        ("omr", "mini_amc.omr.read_scans"),
        ("grades", "mini_amc.grade.notes"),
    )
    for name, mod in cases:
        import importlib

        module = importlib.import_module(mod)
        monkeypatch.setattr(
            module, "main", lambda argv, m=mod: calls.setdefault(m, argv)
        )
        cli.main([name, "--some", "args"])
    assert calls == {
        "mini_amc.gen.generate": ["--some", "args"],
        "mini_amc.omr.read_scans": ["--some", "args"],
        "mini_amc.grade.notes": ["--some", "args"],
    }


def test_web_subcommand(monkeypatch):
    seen = {}

    def fake_run(app, host, port, reload):
        seen.update(app=app, host=host, port=port, reload=reload)

    monkeypatch.setattr(cli.uvicorn, "run", fake_run)
    monkeypatch.delenv("MINI_AMC_DATA", raising=False)
    cli.main(["web", "--port", "9999", "--reload", "--data", "/tmp/exam1/data"])
    assert seen == {
        "app": "mini_amc.web.app:app",
        "host": "127.0.0.1",
        "port": 9999,
        "reload": True,
    }
    assert os.environ["MINI_AMC_DATA"] == str(Path("/tmp/exam1/data").resolve())


def test_unknown_command_errors():
    with pytest.raises(SystemExit):
        cli.main(["nope"])


def test_subcommand_help_passthrough(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["generate", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "usage: mini-amc generate" in out
    assert "--bank" in out
