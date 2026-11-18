import shutil
from pathlib import Path

import pytest

from mini_amc.gen.generate import load_bank

EXAMPLES = Path(__file__).resolve().parents[1] / "src" / "mini_amc" / "examples"
needs_typst = pytest.mark.skipif(
    shutil.which("typst") is None, reason="typst binary not installed"
)


def write_subject(tmp_path: Path, body: str) -> Path:
    shutil.copy(EXAMPLES / "amc.typ", tmp_path / "amc.typ")
    path = tmp_path / "subject.typ"
    path.write_text(body, encoding="utf-8")
    return path


@needs_typst
def test_load_bank_from_typ(tmp_path):
    path = write_subject(
        tmp_path,
        """
#import "amc.typ": exam, question, choice

#show: exam.with(title: "Demo", course: "C1", date: "2026-01-02")

#question(id: "q1", text: "What is $7 times 8$?")[
  #choice("$54$")
  #choice("$56$", correct: true)
]

#question(id: "q2", type: "open", max-points: 3, text: "Explain.")[]
""",
    )
    bank = load_bank(path)
    assert bank["meta"] == {"title": "Demo", "course": "C1", "date": "2026-01-02"}
    assert [q["id"] for q in bank["questions"]] == ["q1", "q2"]
    q1, q2 = bank["questions"]
    assert q1["text"] == "What is $7 times 8$?"
    assert q1["choices"] == [
        {"text": "$54$", "correct": False},
        {"text": "$56$", "correct": True},
    ]
    assert q2["type"] == "open"
    assert q2["max_points"] == 3
    assert "choices" not in q2


@needs_typst
def test_load_bank_from_typ_choice_outside_question(tmp_path):
    path = write_subject(
        tmp_path,
        """
#import "amc.typ": question, choice

#choice("orphan")
#question(id: "q1", text: "Q?")[
  #choice("a")
  #choice("b", correct: true)
]
""",
    )
    with pytest.raises(ValueError, match="outside a multiple-choice"):
        load_bank(path)


@needs_typst
def test_load_bank_from_typ_without_questions(tmp_path):
    path = write_subject(
        tmp_path, '#import "amc.typ": exam\n#show: exam.with(title: "x")\n'
    )
    with pytest.raises(ValueError, match="no #question found"):
        load_bank(path)


@needs_typst
def test_load_bank_from_typ_reports_typst_error(tmp_path):
    path = write_subject(
        tmp_path,
        """
#import "amc.typ": question, choice

#question(text: "no id")[
  #choice("a")
  #choice("b", correct: true)
]
""",
    )
    with pytest.raises(RuntimeError, match="typst eval failed"):
        load_bank(path)


@needs_typst
def test_example_subject_matches_example_bank():
    from_subject = load_bank(EXAMPLES / "subject.example.typ")
    from_yaml = load_bank(EXAMPLES / "bank.example.yml")
    assert from_subject["meta"] == from_yaml["meta"]

    def normalize(bank):
        out = []
        for q in bank["questions"]:
            item = {"id": q["id"], "text": q["text"], "type": q.get("type", "mcq")}
            if item["type"] == "open":
                item["max_points"] = q["max_points"]
            else:
                item["choices"] = [
                    (c["text"], bool(c.get("correct", False))) for c in q["choices"]
                ]
            out.append(item)
        return out

    assert normalize(from_subject) == normalize(from_yaml)
