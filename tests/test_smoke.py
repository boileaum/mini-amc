import shutil
from pathlib import Path

import pytest


def test_load_bank_example():
    from mini_amc.gen.generate import load_bank

    bank = load_bank(Path("src/mini_amc/examples/bank.example.yml"))
    assert len(bank["questions"]) == 5
    assert sum(1 for q in bank["questions"] if q.get("type") == "open") == 1


def test_modules_importables():
    import importlib

    modules = ["mini_amc.gen.generate", "mini_amc.omr.read_scans", "mini_amc.web.app"]
    for name in modules:
        assert importlib.import_module(name) is not None


@pytest.mark.skipif(shutil.which("typst") is None, reason="typst binary required")
def test_compile_fixture(tmp_path):
    import subprocess

    import qrcode

    template = Path("src/mini_amc/template")
    shutil.copy(template / "copy.example.json", template / "copy.json")
    for n in range(1, 65):
        qrcode.make(f"copy:0001|page:{n}").save(template / f"qr-{n}.png")
    try:
        subprocess.run(
            ["typst", "compile", "main.typ", str(tmp_path / "copy.pdf")],
            cwd=template,
            check=True,
        )
        assert (tmp_path / "copy.pdf").stat().st_size > 0
    finally:
        (template / "copy.json").unlink(missing_ok=True)
        for n in range(1, 65):
            (template / f"qr-{n}.png").unlink(missing_ok=True)
