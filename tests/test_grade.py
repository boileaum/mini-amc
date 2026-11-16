import csv
import json

import pytest

from mini_amc.grade.notes import compute_grades, main, question_point, write_csvs


@pytest.fixture()
def data_dir(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    positions = {
        "0001": {
            "bubbles": [
                {"qid": q, "key": k, "page": 1, "x_pt": 1.0, "y_pt": 2.0}
                for q in ("q1", "q2", "q3")
                for k in "ABC"
            ]
            + [
                {"qid": "q4", "value": v, "page": 1, "x_pt": 1.0, "y_pt": 2.0}
                for v in range(3)
            ],
            "gradeboxes": [
                {"qid": "q4", "value": v, "page": 1, "x_pt": 1.0, "y_pt": 2.0}
                for v in range(3)
            ],
        },
        "0002": {
            "bubbles": [
                {"qid": "q1", "key": k, "page": 1, "x_pt": 1.0, "y_pt": 2.0}
                for k in "ABC"
            ]
        },
    }
    (data / "positions.json").write_text(json.dumps(positions), encoding="utf-8")
    answers = {
        "0001": {"q1": "B", "q2": "A", "q3": "A", "q4": "open"},
        "0002": {"q1": "B"},
    }
    (data / "answers.json").write_text(json.dumps(answers), encoding="utf-8")
    copy = {
        "copy_id": "0001",
        "meta": {"title": "T", "course": "T", "date": "2026-11-13"},
        "questions": [
            {"id": "q4", "text": "Explain.", "type": "open", "max_points": 2}
        ],
    }
    (data / "copy_0001.json").write_text(json.dumps(copy), encoding="utf-8")
    omr = {
        "scans": {},
        "copies": {
            "0001": {
                "pages": [1],
                "status": "needs_review",
                "questions": [
                    {
                        "qid": "q1",
                        "fills": {"A": 0.9, "B": 0.8, "C": 0.0},
                        "checked": ["A", "B"],
                        "needs_review": True,
                        "page": 1,
                    },
                    {
                        "qid": "q2",
                        "fills": {"A": 0.95, "B": 0.0, "C": 0.0},
                        "checked": ["A"],
                        "needs_review": False,
                        "page": 1,
                    },
                    {
                        "qid": "q3",
                        "fills": {"A": 0.0, "B": 0.0, "C": 0.9},
                        "checked": ["C"],
                        "needs_review": False,
                        "page": 1,
                    },
                    {
                        "qid": "q4",
                        "type": "open",
                        "fills": {"0": 0.0, "1": 0.0, "2": 0.9},
                        "checked": [2],
                        "needs_review": False,
                        "page": 1,
                    },
                ],
            }
        },
    }
    (data / "omr_results.json").write_text(json.dumps(omr), encoding="utf-8")
    corrections = {"0001": {"q1": ["B"], "q3": ["A"]}}
    (data / "corrections.json").write_text(json.dumps(corrections), encoding="utf-8")
    (data / "students.json").write_text(
        json.dumps({"0001": "Alice Example"}), encoding="utf-8"
    )
    return data


def test_question_point():
    assert question_point(["A"], None, ["A"]) == 1
    assert question_point(["A"], None, ["B"]) == 0
    assert question_point(["A", "B"], None, ["A"]) == 0
    assert question_point([], None, ["A"]) == 0
    assert question_point(["C"], ["A"], ["A"]) == 1
    assert question_point(["A"], ["B"], ["A"]) == 0
    assert question_point(["A"], [], ["A"]) == 0
    # multi-answer: exact set = 1 pt
    assert question_point(["A", "B"], None, ["A", "B"]) == 1
    assert question_point(["B", "A"], None, ["A", "B"]) == 1
    assert question_point(["A"], None, ["A", "B"]) == 0
    assert question_point(["A", "C"], None, ["A", "B"]) == 0


def test_compute_grades(data_dir):
    notes, detail = compute_grades(data_dir)
    by_copy = {n["copy_id"]: n for n in notes}
    assert by_copy["0001"]["score"] == 5
    assert by_copy["0001"]["score_max"] == 5
    assert by_copy["0001"]["status"] == "needs_review"
    assert by_copy["0002"]["score"] == 0
    assert by_copy["0002"]["status"] == "unread"
    d = {(r["copy_id"], r["qid"]): r for r in detail}
    assert d[("0001", "q1")]["point"] == 1
    assert d[("0001", "q1")]["checked"] == "A+B"
    assert d[("0001", "q1")]["correction"] == "B"
    assert d[("0001", "q2")]["point"] == 1
    assert d[("0001", "q3")]["point"] == 1
    assert d[("0001", "q3")]["correction"] == "A"
    assert d[("0001", "q4")]["point"] == 2
    assert d[("0001", "q4")]["type"] == "open"
    assert d[("0001", "q4")]["checked"] == "2"
    assert d[("0002", "q1")]["checked"] == ""
    assert d[("0002", "q1")]["point"] == 0
    assert d[("0002", "q1")]["page"] == ""


def test_write_csvs(data_dir):
    notes, detail = compute_grades(data_dir)
    notes_path, detail_path = write_csvs(data_dir, notes, detail)
    with notes_path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0] == {
        "copy_id": "0001",
        "student": "Alice Example",
        "status": "needs_review",
        "bareme": "v1",
        "score": "5",
        "score_max": "5",
    }
    assert rows[1]["copy_id"] == "0002" and rows[1]["score"] == "0"
    assert rows[1]["student"] == ""
    with detail_path.open(encoding="utf-8", newline="") as f:
        drows = list(csv.DictReader(f))
    assert len(drows) == 5
    q1 = next(r for r in drows if r["qid"] == "q1" and r["copy_id"] == "0001")
    assert (
        q1["point"] == "1" and q1["correction"] == "B" and q1["needs_review"] == "True"
    )


def test_main(data_dir, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["mini-amc-grades", "--data", str(data_dir)])
    main()
    out = capsys.readouterr().out
    assert "2 copies" in out and "5 pts total" in out
    assert (data_dir / "notes.csv").exists()
    assert (data_dir / "notes_detail.csv").exists()


def test_main_empty_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["mini-amc-grades", "--data", str(tmp_path)])
    main()
    with (tmp_path / "notes.csv").open(encoding="utf-8", newline="") as f:
        assert list(csv.DictReader(f)) == []


def test_question_point_open():
    assert question_point([2], None, "open", 2) == 2
    assert question_point([], [1], "open", 2) == 1
    assert question_point([5], None, "open", 2) == 0
    assert question_point(["x"], None, "open", 2) == 0
    assert question_point([], None, "open", None) == 0
    assert question_point([0, 1], None, "open", 2) == 0
    assert question_point(["A"], None, "A", None) == 1


def test_bareme_schemes():
    from mini_amc.grade.notes import BAREMES

    assert set(BAREMES) == {"v1", "amc"}
    # v1: exact set
    assert question_point(["A", "B"], None, ["A", "B"], scheme="v1") == 1
    assert question_point(["A"], None, ["A", "B"], scheme="v1") == 0
    # amc: +1 good, -1 wrong, floored at 0
    assert question_point(["A", "B"], None, ["A", "B"], scheme="amc") == 2
    assert question_point(["A", "C"], None, ["A", "B"], scheme="amc") == 0
    assert question_point(["C"], None, ["A"], scheme="amc") == 0
    assert question_point(["A"], None, ["A"], scheme="amc") == 1
    with pytest.raises(ValueError, match="unknown bareme"):
        question_point(["A"], None, ["A"], scheme="nope")


def test_load_bareme_config(tmp_path):
    from mini_amc.grade.notes import load_bareme

    assert load_bareme(tmp_path) == "v1"
    (tmp_path / "config.json").write_text('{"bareme": "amc"}', encoding="utf-8")
    assert load_bareme(tmp_path) == "amc"
    (tmp_path / "config.json").write_text('{"bareme": "nope"}', encoding="utf-8")
    with pytest.raises(ValueError, match="unknown bareme"):
        load_bareme(tmp_path)


def test_grades_bareme_column_and_flag(data_dir, monkeypatch):
    (data_dir / "config.json").write_text('{"bareme": "amc"}', encoding="utf-8")
    notes, detail = compute_grades(data_dir)
    assert all(n["bareme"] == "amc" for n in notes)
    notes_path, _ = write_csvs(data_dir, notes, detail)
    with notes_path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["bareme"] == "amc"
    # CLI flag overrides the config
    monkeypatch.setattr(
        "sys.argv", ["mini-amc-grades", "--data", str(data_dir), "--bareme", "v1"]
    )
    main()
    with notes_path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["bareme"] == "v1"
