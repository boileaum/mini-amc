"""Grading (bareme v1) and CSV export of the exam results."""

import argparse
import csv
import json
from pathlib import Path

NOTES_CSV = "notes.csv"
DETAIL_CSV = "notes_detail.csv"


def question_point(checked: list, correction: list | None, expected: str | None) -> int:
    """
    Points for one question (bareme v1: 1 pt per correct answer, no negative points).

    The effective answer is the manual correction if present, else the
    OMR-checked keys.

    Args:
        checked: OMR-checked choice keys.
        correction: Manual correction (list of keys) or ``None``.
        expected: Expected key from the answer key.

    Returns:
        1 if exactly one effective key and it equals ``expected``, else 0.
    """
    effective = correction if correction is not None else checked
    return 1 if len(effective) == 1 and effective[0] == expected else 0


def _load(data: Path, name: str, default):
    path = data / name
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def compute_grades(data: Path) -> tuple[list[dict], list[dict]]:
    """
    Compute the grades of all copies found in a data directory.

    Args:
        data: Data directory with ``positions.json``, ``answers.json``,
            ``omr_results.json`` and optionally ``corrections.json``.

    Returns:
        Tuple ``(notes, detail)``: one notes row per copy (``copy_id``,
        ``student`` (empty without ``students.json``), ``status``,
        ``score``, ``score_max``) and one detail row per
        copy/question (``copy_id``, ``qid``, ``page``, ``checked``,
        ``correction``, ``expected``, ``point``, ``needs_review``).
    """
    positions = _load(data, "positions.json", {})
    answers = _load(data, "answers.json", {})
    omr = _load(data, "omr_results.json", {"scans": {}, "copies": {}})
    corrections = _load(data, "corrections.json", {})
    students = _load(data, "students.json", {})
    notes = []
    detail = []
    for copy_id in sorted(positions):
        expected_map = answers.get(copy_id, {})
        omr_copy = omr["copies"].get(copy_id)
        omr_q = {q["qid"]: q for q in omr_copy["questions"]} if omr_copy else {}
        corr = corrections.get(copy_id, {})
        status = omr_copy["status"] if omr_copy else "unread"
        score = 0
        for qid, expected in expected_map.items():
            q = omr_q.get(qid)
            checked = list(q["checked"]) if q else []
            correction = corr.get(qid)
            point = question_point(checked, correction, expected)
            score += point
            detail.append(
                {
                    "copy_id": copy_id,
                    "qid": qid,
                    "page": q["page"] if q else "",
                    "checked": "+".join(checked),
                    "correction": "+".join(correction) if correction else "",
                    "expected": expected,
                    "point": point,
                    "needs_review": q["needs_review"] if q else False,
                }
            )
        notes.append(
            {
                "copy_id": copy_id,
                "student": students.get(copy_id, ""),
                "status": status,
                "score": score,
                "score_max": len(expected_map),
            }
        )
    return notes, detail


def write_csvs(data: Path, notes: list[dict], detail: list[dict]) -> tuple[Path, Path]:
    """
    Write ``notes.csv`` and ``notes_detail.csv`` into the data directory.

    Args:
        data: Data directory.
        notes: Notes rows from ``compute_grades``.
        detail: Detail rows from ``compute_grades``.

    Returns:
        Paths of the two written CSV files.
    """
    notes_path = data / NOTES_CSV
    detail_path = data / DETAIL_CSV
    with notes_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["copy_id", "student", "status", "score", "score_max"]
        )
        writer.writeheader()
        writer.writerows(notes)
    with detail_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "copy_id",
                "qid",
                "page",
                "checked",
                "correction",
                "expected",
                "point",
                "needs_review",
            ],
        )
        writer.writeheader()
        writer.writerows(detail)
    return notes_path, detail_path


def main() -> None:
    """CLI entry point ``mini-amc-grades``: compute the grades and write the CSVs."""
    ap = argparse.ArgumentParser(description="Grades (bareme v1) + CSV export")
    ap.add_argument("--data", type=Path, default=Path("data"))
    args = ap.parse_args()
    notes, detail = compute_grades(args.data)
    notes_path, detail_path = write_csvs(args.data, notes, detail)
    total = sum(n["score"] for n in notes)
    print(
        f"wrote {notes_path} ({len(notes)} copies, {total} pts total) "
        f"and {detail_path} ({len(detail)} rows)"
    )


if __name__ == "__main__":
    main()
