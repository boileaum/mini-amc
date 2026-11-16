"""Grading (bareme v1) and CSV export of the exam results."""

import argparse
import csv
import json
from pathlib import Path

NOTES_CSV = "notes.csv"
DETAIL_CSV = "notes_detail.csv"
CONFIG_JSON = "config.json"
DEFAULT_BAREME = "v1"


def _bareme_v1(effective: list, expected: list[str], max_points: int | None) -> int:
    """v1: 1 pt iff the checked set equals the expected set, else 0."""
    return 1 if set(effective) == set(expected) else 0


def _bareme_amc(effective: list, expected: list[str], max_points: int | None) -> int:
    """AMC-style: +1 per correct checked, -1 per wrong checked, floored at 0."""
    exp = set(expected)
    good = len(set(effective) & exp)
    bad = len(set(effective) - exp)
    return max(0, good - bad)


# named grading schemes for MCQ questions; open questions always score their
# (blackened/corrected) box value in [0, max_points], whatever the scheme
BAREMES = {"v1": _bareme_v1, "amc": _bareme_amc}


def load_bareme(data: Path) -> str:
    """
    Read the grading scheme of a project from ``data/config.json``.

    Args:
        data: Project data directory.

    Returns:
        The scheme name (``DEFAULT_BAREME`` if no config file).

    Raises:
        ValueError: Unknown scheme name in the config file.
    """
    path = data / CONFIG_JSON
    if not path.exists():
        return DEFAULT_BAREME
    scheme = json.loads(path.read_text(encoding="utf-8")).get("bareme", DEFAULT_BAREME)
    if scheme not in BAREMES:
        raise ValueError(
            f"unknown bareme {scheme!r} in {path} (known: {sorted(BAREMES)})"
        )
    return scheme


def question_point(
    checked: list,
    correction: list | None,
    expected: str | list[str] | None,
    max_points: int | None = None,
    scheme: str = DEFAULT_BAREME,
) -> int:
    """
    Points for one question under a named grading scheme.

    MCQ: the scheme function from ``BAREMES`` (``expected`` is a list of
    keys — one for single-answer, several for multi-answer).
    Open question (``expected == "open"``): the graded value (the blackened
    grade box, or the manual correction), clamped to [0, ``max_points``] —
    identical for all schemes.

    The effective answer is the manual correction if present, else the
    OMR-checked keys/value.

    Args:
        checked: OMR-checked choice keys (MCQ) or graded value (open).
        correction: Manual correction (list) or ``None``.
        expected: Expected keys from the answer key (list), or ``"open"``.
        max_points: Maximum points of an open question.
        scheme: Name of a scheme in ``BAREMES``.

    Returns:
        The points for the question.

    Raises:
        ValueError: Unknown scheme name.
    """
    if scheme not in BAREMES:
        raise ValueError(f"unknown bareme {scheme!r} (known: {sorted(BAREMES)})")
    effective = correction if correction is not None else checked
    if expected == "open":
        if len(effective) == 1 and max_points is not None:
            try:
                # int() tolerates string values from a hand-edited corrections.json
                v = int(effective[0])
            except (TypeError, ValueError):
                return 0
            return v if 0 <= v <= max_points else 0
        return 0
    if expected is None:
        return 0
    expected_keys = list(expected) if isinstance(expected, list) else [expected]
    return BAREMES[scheme](effective, expected_keys, max_points)


def _load(data: Path, name: str, default):
    path = data / name
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def compute_grades(
    data: Path, scheme: str | None = None
) -> tuple[list[dict], list[dict]]:
    """
    Compute the grades of all copies found in a data directory.

    Args:
        data: Data directory with ``positions.json``, ``answers.json``,
            ``omr_results.json`` and optionally ``corrections.json``.
        scheme: Grading scheme name (``BAREMES``); if ``None``, read from
            ``data/config.json`` (default ``v1``).

    Returns:
        Tuple ``(notes, detail)``: one notes row per copy (``copy_id``,
        ``student`` (empty without ``students.json``), ``status``,
        ``bareme``, ``score``, ``score_max``) and one detail row per
        copy/question (``copy_id``, ``qid``, ``type``, ``page``, ``checked``,
        ``correction``, ``expected``, ``point``, ``needs_review``).
        ``score_max`` counts 1 per MCQ and ``max_points`` per open question.
    """
    scheme = scheme or load_bareme(data)
    positions = _load(data, "positions.json", {})
    answers = _load(data, "answers.json", {})
    omr = _load(data, "omr_results.json", {"scans": {}, "copies": {}})
    corrections = _load(data, "corrections.json", {})
    students = _load(data, "students.json", {})
    notes = []
    detail = []
    for copy_id in sorted(positions):
        expected_map = answers.get(copy_id, {})
        content = _load(data, f"copy_{copy_id}.json", None)
        qmeta = {q["id"]: q for q in content["questions"]} if content else {}
        omr_copy = omr["copies"].get(copy_id)
        omr_q = {q["qid"]: q for q in omr_copy["questions"]} if omr_copy else {}
        corr = corrections.get(copy_id, {})
        status = omr_copy["status"] if omr_copy else "unread"
        score = 0
        score_max = 0
        for qid, expected in expected_map.items():
            q = omr_q.get(qid)
            checked = list(q["checked"]) if q else []
            correction = corr.get(qid)
            is_open = expected == "open"
            max_points = qmeta.get(qid, {}).get("max_points") if is_open else None
            point = question_point(checked, correction, expected, max_points, scheme)
            score += point
            score_max += max_points if is_open and max_points else 1
            detail.append(
                {
                    "copy_id": copy_id,
                    "qid": qid,
                    "type": "open" if is_open else "mcq",
                    "page": q["page"] if q else "",
                    "checked": "+".join(str(c) for c in checked),
                    "correction": "+".join(str(c) for c in correction)
                    if correction
                    else "",
                    "expected": expected if expected == "open" else "+".join(expected),
                    "point": point,
                    "needs_review": q["needs_review"] if q else False,
                }
            )
        notes.append(
            {
                "copy_id": copy_id,
                "student": students.get(copy_id, ""),
                "status": status,
                "bareme": scheme,
                "score": score,
                "score_max": score_max,
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
            f,
            fieldnames=["copy_id", "student", "status", "bareme", "score", "score_max"],
        )
        writer.writeheader()
        writer.writerows(notes)
    with detail_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "copy_id",
                "qid",
                "type",
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


def main(argv: list[str] | None = None) -> None:
    """Subcommand ``mini-amc grades``: compute grades, write the CSVs."""
    ap = argparse.ArgumentParser(
        prog="mini-amc grades",
        description="Grades (named baremes) + CSV export",
    )
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument(
        "--bareme",
        choices=sorted(BAREMES),
        default=None,
        help="grading scheme (default: data/config.json, else v1)",
    )
    args = ap.parse_args(argv)
    notes, detail = compute_grades(args.data, args.bareme)
    notes_path, detail_path = write_csvs(args.data, notes, detail)
    total = sum(n["score"] for n in notes)
    print(
        f"wrote {notes_path} ({len(notes)} copies, {total} pts total) "
        f"and {detail_path} ({len(detail)} rows)"
    )


if __name__ == "__main__":
    main()
