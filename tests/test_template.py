import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("typst") is None, reason="typst binary required"
)

MAX_PAGES = 64
N_QUESTIONS = 40


def _build_copy(dir_path: Path) -> None:
    shutil.copy(Path("src/mini_amc/template/main.typ"), dir_path / "main.typ")
    questions: list[dict] = [
        {
            "id": f"q{i}",
            "text": f"Question number {i}?",
            "type": "mcq",
            "choices": [
                {"key": "A", "text": f"choice A {i}", "correct": False},
                {"key": "B", "text": f"choice B {i}", "correct": True},
                {"key": "C", "text": f"choice C {i}", "correct": False},
            ],
        }
        for i in range(1, N_QUESTIONS + 1)
    ]
    questions.append(
        {
            "id": "qopen",
            "text": "Explain something.",
            "type": "open",
            "max_points": 3,
        }
    )
    copy = {
        "copy_id": "9999",
        "meta": {"title": "Test", "course": "T", "date": "2026-11-13"},
        "questions": questions,
    }
    (dir_path / "copy.json").write_text(json.dumps(copy), encoding="utf-8")
    import qrcode

    for n in range(1, MAX_PAGES + 1):
        qrcode.make(f"copy:9999|page:{n}").save(dir_path / f"qr-{n}.png")


def _query_metadata(dir_path: Path) -> list:
    out = subprocess.run(
        ["typst", "eval", "query(metadata).map(it => it.value)", "--in", "main.typ"],
        cwd=dir_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(out)


def test_multipage_and_positions(tmp_path):
    _build_copy(tmp_path)
    subprocess.run(
        ["typst", "compile", "main.typ", "copy.pdf"], cwd=tmp_path, check=True
    )
    metas = _query_metadata(tmp_path)
    bubbles = [m for m in metas if m["kind"] == "bubble"]
    gradeboxes = [m for m in metas if m["kind"] == "gradebox"]
    questions = [m for m in metas if m["kind"] == "question"]
    assert len(questions) == N_QUESTIONS + 1
    assert len(bubbles) == N_QUESTIONS * 3
    assert len(gradeboxes) == 4
    assert sorted(g["value"] for g in gradeboxes) == [0, 1, 2, 3]
    assert all(g["qid"] == "qopen" for g in gradeboxes)
    assert max(b["page"] for b in bubbles) >= 2
    for b in bubbles + gradeboxes:
        assert b["x"].endswith("pt")
        assert b["y"].endswith("pt")
        assert b["page"] >= 1
        assert b["copy"] == "9999"
