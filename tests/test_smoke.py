import shutil
import sys
from pathlib import Path

import pytest


def test_load_bank_example():
    from mini_amc.gen.generate import load_bank

    bank = load_bank(Path("bank.example.yml"))
    assert len(bank["questions"]) == 4


def test_modules_importables():
    import importlib

    modules = ["mini_amc.gen.generate", "mini_amc.omr.read_scans", "mini_amc.web.app"]
    for name in modules:
        assert importlib.import_module(name) is not None


@pytest.mark.skipif(shutil.which("typst") is None, reason="binaire typst requis")
def test_compile_fixture(tmp_path):
    import subprocess

    template = Path("template")
    shutil.copy(template / "copy.example.json", template / "copy.json")
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import qrcode; qrcode.make('copy:0001|page:1').save('template/qr.png')",
        ],
        check=True,
    )
    try:
        subprocess.run(
            ["typst", "compile", "main.typ", str(tmp_path / "copy.pdf")],
            cwd=template,
            check=True,
        )
        assert (tmp_path / "copy.pdf").stat().st_size > 0
    finally:
        (template / "copy.json").unlink(missing_ok=True)
        (template / "qr.png").unlink(missing_ok=True)
