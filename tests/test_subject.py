import shutil
from pathlib import Path

import pytest

from mini_amc.gen.generate import load_bank

EXAMPLES = Path(__file__).resolve().parents[1] / "src" / "mini_amc" / "examples"
needs_typst = pytest.mark.skipif(
    shutil.which("typst") is None, reason="typst binary not installed"
)


def write_raw_subject(tmp_path: Path, body: str) -> Path:
    shutil.copy(EXAMPLES / "amc.typ", tmp_path / "amc.typ")
    path = tmp_path / "subject.typ"
    path.write_text(body, encoding="utf-8")
    return path


@needs_typst
def test_load_bank(tmp_path):
    path = write_raw_subject(
        tmp_path,
        """
#import "amc.typ": exam, question, choice, render

#let bank = exam(
  title: "Demo",
  course: "C1",
  date: "2026-01-02",
  questions: (
    question(id: "q1", text: [What is $7 times 8$?], choices: (
      choice([$54$]),
      choice([$56$], correct: true),
    )),
    question(id: "q2", type: "open", max-points: 3, text: "Explain."),
  ),
)

#render(bank)
""",
    )
    bank = load_bank(path)
    assert bank["meta"] == {"title": "Demo", "course": "C1", "date": "2026-01-02"}
    assert [q["id"] for q in bank["questions"]] == ["q1", "q2"]
    q1, q2 = bank["questions"]
    assert q1["text"] == "What is $7 × 8$?"
    assert q1["choices"] == [
        {"text": "$54$", "correct": False},
        {"text": "$56$", "correct": True},
    ]
    assert q2["type"] == "open"
    assert q2["max_points"] == 3
    assert "choices" not in q2


@needs_typst
def test_load_bank_flattens_markup(tmp_path):
    path = write_raw_subject(
        tmp_path,
        """
#import "amc.typ": exam, question, choice

#let bank = exam(questions: (
  question(id: "q1", text: [A *strong* word and a list:
    - one
    - two], choices: (choice("a"), choice("b", correct: true))),
))
""",
    )
    bank = load_bank(path)
    text = bank["questions"][0]["text"]
    assert text.startswith("A strong word and a list:")
    assert "one" in text and "two" in text


@needs_typst
def test_load_bank_asserts_bad_question(tmp_path):
    path = write_raw_subject(
        tmp_path,
        """
#import "amc.typ": exam, question, choice

#let bank = exam(questions: (
  question(id: "q1", type: "open", max-points: 2, choices: (choice("a"))),
))
""",
    )
    with pytest.raises(RuntimeError, match="typst eval failed"):
        load_bank(path)


@needs_typst
def test_load_bank_without_questions(tmp_path):
    path = write_raw_subject(
        tmp_path, '#import "amc.typ": exam\n#let bank = exam(title: "x")\n'
    )
    with pytest.raises(ValueError, match="no #question found"):
        load_bank(path)


@needs_typst
def test_load_bank_reports_typst_error(tmp_path):
    path = write_raw_subject(
        tmp_path,
        """
#import "amc.typ": exam, question, choice

#let bank = exam(questions: (
  question(text: "no id", choices: (choice("a"), choice("b", correct: true))),
))
""",
    )
    with pytest.raises(RuntimeError, match="typst eval failed"):
        load_bank(path)


@needs_typst
def test_load_bank_without_bank(tmp_path):
    path = write_raw_subject(tmp_path, '#import "amc.typ": exam\n#show: exam.with()\n')
    with pytest.raises(RuntimeError, match="typst eval failed"):
        load_bank(path)


@needs_typst
def test_load_bank_splits_files(tmp_path):
    (tmp_path / "q").mkdir()
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "snippet.py").write_text("print(1)\n", encoding="utf-8")
    (tmp_path / "q" / "chapter.typ").write_text(
        """
#import "../amc.typ": choice, question

#let questions = (
  question(id: "q2", text: [What does this print?
    #raw(read("../code/snippet.py", encoding: "utf8"), lang: "python")],
    choices: (choice("1", correct: true), choice("2"))),
)
""",
        encoding="utf-8",
    )
    path = write_raw_subject(
        tmp_path,
        """
#import "amc.typ": exam, question, choice
#import "q/chapter.typ": questions as chapter

#let bank = exam(questions: (
  question(id: "q1", text: "First?", choices: (
    choice("a"),
    choice("b", correct: true),
  )),
) + chapter)
""",
    )
    bank = load_bank(path)
    assert [q["id"] for q in bank["questions"]] == ["q1", "q2"]
    assert "print(1)" in bank["questions"][1]["text"]


@needs_typst
def test_example_subject_loads():
    bank = load_bank(EXAMPLES / "subject.typ")
    assert bank["meta"] == {
        "title": "Demo exam",
        "course": "Demo 101",
        "date": "2026-11-12",
    }
    by_id = {q["id"]: q for q in bank["questions"]}
    assert list(by_id) == ["q1", "q2", "q3", "q4", "q5", "q6"]
    assert by_id["q3"]["text"] == "What is $7 × 8$?"
    assert by_id["q5"]["type"] == "open"
    assert by_id["q5"]["max_points"] == 2
    assert "choices" not in by_id["q5"]
    # q6 comes from the chapter file and shows an external code file
    assert "print" in by_id["q6"]["text"]
    assert by_id["q1"]["choices"][0] == {"text": "Paris", "correct": True}
