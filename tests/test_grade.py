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
        "0001": {"q1": "B", "q2": "A", "q3": "A"},
        "0002": {"q1": "B"},
    }
    (data / "answers.json").write_text(json.dumps(answers), encoding="utf-8")
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
    assert question_point(["A"], None, "A") == 1
    assert question_point(["A"], None, "B") == 0
    assert question_point(["A", "B"], None, "A") == 0
    assert question_point([], None, "A") == 0
    assert question_point(["C"], ["A"], "A") == 1
    assert question_point(["A"], ["B"], "A") == 0
    assert question_point(["A"], [], "A") == 0


def test_compute_grades(data_dir):
    notes, detail = compute_grades(data_dir)
    by_copy = {n["copy_id"]: n for n in notes}
    assert by_copy["0001"]["score"] == 3
    assert by_copy["0001"]["score_max"] == 3
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
        "score": "3",
        "score_max": "3",
    }
    assert rows[1]["copy_id"] == "0002" and rows[1]["score"] == "0"
    assert rows[1]["student"] == ""
    with detail_path.open(encoding="utf-8", newline="") as f:
        drows = list(csv.DictReader(f))
    assert len(drows) == 4
    q1 = next(r for r in drows if r["qid"] == "q1" and r["copy_id"] == "0001")
    assert (
        q1["point"] == "1" and q1["correction"] == "B" and q1["needs_review"] == "True"
    )


def test_main(data_dir, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["mini-amc-grades", "--data", str(data_dir)])
    main()
    out = capsys.readouterr().out
    assert "2 copies" in out and "3 pts total" in out
    assert (data_dir / "notes.csv").exists()
    assert (data_dir / "notes_detail.csv").exists()


def test_main_empty_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["mini-amc-grades", "--data", str(tmp_path)])
    main()
    with (tmp_path / "notes.csv").open(encoding="utf-8", newline="") as f:
        assert list(csv.DictReader(f)) == []
