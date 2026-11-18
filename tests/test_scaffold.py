import pytest

from mini_amc.scaffold import EXAMPLE_FILES, init_project, main


def test_init_creates_example_files(tmp_path):
    target = tmp_path / "exam"
    written = init_project(target)
    assert {p.relative_to(target).as_posix() for p in written} == set(EXAMPLE_FILES) | {
        ".gitignore"
    }
    for name in EXAMPLE_FILES:
        assert (target / name).exists()
    bank = (target / "bank.example.yml").read_text(encoding="utf-8")
    assert "questions:" in bank
    gitignore = (target / ".gitignore").read_text(encoding="utf-8")
    assert "data/" in gitignore
    assert "scans/" in gitignore


def test_init_does_not_overwrite(tmp_path):
    target = tmp_path / "exam"
    init_project(target)
    (target / "bank.example.yml").write_text("custom", encoding="utf-8")
    with pytest.raises(FileExistsError):
        init_project(target)
    assert (target / "bank.example.yml").read_text(encoding="utf-8") == "custom"
    init_project(target, force=True)
    assert (target / "bank.example.yml").read_text(encoding="utf-8") != "custom"


def test_init_main(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["mini-amc-init", str(tmp_path / "exam2")])
    main()
    out = capsys.readouterr().out
    assert "bank.example.yml" in out
    assert (tmp_path / "exam2" / "runbook.md").exists()
    assert (tmp_path / "exam2" / ".gitignore").exists()
