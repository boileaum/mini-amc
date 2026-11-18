import json
import shutil
from pathlib import Path

import pytest


def test_load_bank_example():
    from mini_amc.gen.generate import load_bank

    bank = load_bank(Path("src/mini_amc/examples/subject.typ"))
    assert len(bank["questions"]) == 6
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
    subject = Path("src/mini_amc/examples/subject.typ").resolve()
    shutil.copy(template / "main.typ", tmp_path / "main.typ")
    shutil.copy(template / "copy.example.json", tmp_path / "copy.json")
    # the template imports `bank`: point it at the example subject (the build
    # dir is a throwaway one, so the import is absolute and the root is /)
    (tmp_path / "bank.typ").write_text(
        f"#import {json.dumps(subject.as_posix())}: bank\n", encoding="utf-8"
    )
    for n in range(1, 65):
        qrcode.make(f"copy:0001|page:{n}").save(tmp_path / f"qr-{n}.png")
    subprocess.run(
        ["typst", "compile", "main.typ", str(tmp_path / "copy.pdf"), "--root", "/"],
        cwd=tmp_path,
        check=True,
    )
    assert (tmp_path / "copy.pdf").stat().st_size > 0
