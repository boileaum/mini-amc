"""FastAPI review UI: copy list, annotated detail, manual corrections."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from mini_amc.grade.notes import load_bareme, question_point

app = FastAPI(title="mini-amc review")

# conventional data directory of the current project: ./data in the working
# directory, overridable with the MINI_AMC_DATA env var (set by
# `mini-amc web --data …`) - one common name for all exam projects
DATA = Path(os.environ.get("MINI_AMC_DATA", Path.cwd() / "data"))
CORRECTIONS_FILE = "corrections.json"


def load_json(name: str, default: Any = None) -> Any:
    """
    Load a JSON file from ``data/``.

    Args:
        name: File name (e.g. ``omr_results.json``).
        default: Value returned if the file does not exist; if ``None``
            and the file is missing, a 404 is raised instead.

    Returns:
        Decoded JSON content, or ``default``.

    Raises:
        HTTPException: 404 if the file is missing and no default is given.
    """
    path = DATA / name
    if not path.exists():
        if default is not None:
            return default
        raise HTTPException(
            status_code=404, detail=f"{name} not found (run the previous step first)"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(name: str, content: dict) -> None:
    """
    Write a JSON file to ``data/`` atomically (temp file + rename).

    Args:
        name: File name (e.g. ``corrections.json``).
        content: JSON-serializable content.
    """
    path = DATA / name
    path.parent.mkdir(parents=True, exist_ok=True)
    # write to a temp file + rename: a crash mid-write must never leave a
    # truncated corrections.json
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(content, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _omr() -> dict:
    return load_json("omr_results.json", default={"scans": {}, "copies": {}})


def _corrections() -> dict:
    return load_json(CORRECTIONS_FILE, default={})


def _positions() -> dict:
    return load_json("positions.json", default={})


def _answers() -> dict:
    return load_json("answers.json", default={})


def _students() -> dict:
    return load_json("students.json", default={})


def _copy_status(copy_id: str, positions: dict, omr_copies: dict) -> dict:
    expected_pages = sorted(
        {b["page"] for b in positions[copy_id]["bubbles"]}
        | {g["page"] for g in positions[copy_id].get("gradeboxes", [])}
    )
    expected_qids = {b["qid"] for b in positions[copy_id]["bubbles"]} | {
        g["qid"] for g in positions[copy_id].get("gradeboxes", [])
    }
    entry = {
        "copy_id": copy_id,
        "student": _students().get(copy_id, ""),
        "status": "unread",
        "pages": [],
        "pages_expected": expected_pages,
        "questions_read": 0,
        "questions_total": len(expected_qids),
    }
    if copy_id in omr_copies:
        c = omr_copies[copy_id]
        entry["status"] = c["status"]
        entry["pages"] = c["pages"]
        entry["questions_read"] = len(c["questions"])
    return entry


def _score(questions: list[dict], answers: dict) -> int:
    # MINI_AMC_BAREME (set by `mini-amc web --bareme`) overrides data/config.json
    scheme = os.environ.get("MINI_AMC_BAREME") or load_bareme(DATA)
    return sum(
        question_point(
            q["checked"],
            q["correction"],
            answers.get(q["qid"]),
            q.get("max_points"),
            scheme,
        )
        for q in questions
    )


def _copy_detail(copy_id: str) -> dict:
    positions = _positions()
    if copy_id not in positions:
        raise HTTPException(status_code=404, detail=f"unknown copy_id {copy_id}")
    content = load_json(f"copy_{copy_id}.json")
    omr = _omr()
    omr_copy = omr["copies"].get(copy_id)
    omr_questions = {q["qid"]: q for q in omr_copy["questions"]} if omr_copy else {}
    corrections = _corrections().get(copy_id, {})
    answers = _answers().get(copy_id, {})
    scans = {
        str(s["page"]): s["scan"]
        for s in omr["scans"].values()
        if s.get("copy_id") == copy_id and s["status"] != "unread"
    }
    questions = []
    score_max = 0
    for q in content["questions"]:
        qid = q["id"]
        is_open = q.get("type", "mcq") == "open"
        mp = q.get("max_points")
        score_max += mp if is_open and isinstance(mp, int) else 1
        omr_q = omr_questions.get(qid)
        questions.append(
            {
                "qid": qid,
                "text": q["text"],
                "type": "open" if is_open else "mcq",
                "max_points": q.get("max_points"),
                "choices": (
                    []
                    if is_open
                    else [
                        {"key": c["key"], "text": c["text"], "correct": c["correct"]}
                        for c in q["choices"]
                    ]
                ),
                "page": omr_q["page"] if omr_q else None,
                "checked": list(omr_q["checked"]) if omr_q else [],
                "fills": omr_q["fills"] if omr_q else {},
                "needs_review": omr_q["needs_review"] if omr_q else False,
                "expected": answers.get(qid),
                "correction": corrections.get(qid),
            }
        )
    status = _copy_status(copy_id, positions, omr["copies"])
    return {
        "copy_id": copy_id,
        "student": _students().get(copy_id, ""),
        "status": status["status"],
        "pages": status["pages"],
        "pages_expected": status["pages_expected"],
        "scans": scans,
        "questions": questions,
        "corrected": len(corrections),
        "score": _score(questions, answers),
        "score_max": score_max,
    }


@app.get("/")
def index() -> dict:
    """
    Service info and endpoint list.

    Returns:
        Dict with the service name and the available endpoints.
    """
    return {
        "service": "mini-amc review",
        "docs": "/docs",
        "endpoints": [
            "GET /copies",
            "GET /copy/{copy_id}",
            "GET /copy/{copy_id}/scan/{page}",
            "POST /copy/{copy_id}/correction",
        ],
    }


@app.get("/copies")
def list_copies() -> dict:
    """
    List the copies with their review status.

    Statuses: ``ok`` / ``needs_review`` / ``partial`` / ``unread``.
    A copy known from ``positions.json`` but absent from the OMR results
    is ``unread``. Only the non-``ok`` copies need a human review; ``ok``
    copies are final (corrections remain possible as overrides).

    Returns:
        Dict with a ``copies`` list (one entry per copy: status, pages
        read vs expected, questions read vs total, number of manual
        corrections).
    """
    positions = _positions()
    omr_copies = _omr()["copies"]
    corrections = _corrections()
    copies = []
    for copy_id in sorted(positions):
        entry = _copy_status(copy_id, positions, omr_copies)
        entry["corrected"] = len(corrections.get(copy_id, {}))
        copies.append(entry)
    return {"copies": copies}


@app.get("/copy/{copy_id}")
def copy_detail(copy_id: str) -> dict:
    """
    Copy detail: detected choices, expected answers, ongoing corrections.

    Args:
        copy_id: Copy identifier (e.g. ``0001``).

    Returns:
        Dict with the copy status, its scans per page, one entry per
        question (text, choices, OMR-checked keys, fills, needs_review,
        expected key, manual correction) and the current score.

    A 404 is returned if the copy_id is unknown (raised by the helper).
    """
    return _copy_detail(copy_id)


@app.get("/copy/{copy_id}/scan/{page}")
def copy_scan(copy_id: str, page: int):
    """
    Annotated scan of one page of a copy (markers, QR, detected bubbles).

    Args:
        copy_id: Copy identifier (e.g. ``0001``).
        page: Page number (1-based).

    Returns:
        The annotated image file (falls back to the raw scan if the
        annotated image is missing).

    Raises:
        HTTPException: 404 if no readable scan exists for this copy/page.
    """
    # one scan per (copy, page): stop at the first match, whether it yields
    # an image (return) or not (unread / missing file -> 404 below)
    for s in _omr()["scans"].values():
        if s.get("copy_id") != copy_id or s.get("page") != page:
            continue
        if s["status"] == "unread":
            break
        # prefer the annotated image, fall back to the raw scan
        for candidate in (s.get("annotated"), os.path.join("scans", s["scan"])):
            if not candidate:
                continue
            path = Path(candidate)
            if not path.is_absolute():
                path = DATA.parent / path
            if path.exists():
                return FileResponse(path)
        break
    raise HTTPException(
        status_code=404, detail=f"no scan for copy {copy_id} page {page}"
    )


@app.post("/copy/{copy_id}/correction")
def post_correction(copy_id: str, payload: dict) -> dict:
    """
    Save a manual correction and recompute the copy's score.

    Args:
        copy_id: Copy identifier.
        payload: ``{"qid": "q1", "checked": ["B"]}`` - an empty ``checked``
            list clears the correction for that question.

    Returns:
        The updated copy detail (see ``GET /copy/{copy_id}``), with the
        recomputed score.

    Raises:
        HTTPException: 404 if the copy or the qid is unknown; 422 if
            ``checked`` is not a list of distinct valid choice keys.
    """
    content = load_json(f"copy_{copy_id}.json")
    qid = payload.get("qid")
    checked = payload.get("checked", [])
    question = next((q for q in content["questions"] if q["id"] == qid), None)
    if question is None:
        raise HTTPException(status_code=404, detail=f"unknown qid {qid}")
    if question.get("type", "mcq") == "open":
        max_points = question.get("max_points", 0)
        valid = (
            isinstance(checked, list)
            and all(
                # bool is a subclass of int: True would pass as 1, exclude it
                isinstance(k, int) and not isinstance(k, bool) and 0 <= k <= max_points
                for k in checked
            )
            and len(set(checked)) == len(checked)
        )
        if not valid:
            raise HTTPException(
                status_code=422,
                detail=f"checked must be distinct integer values in [0, {max_points}]",
            )
    else:
        valid_keys = {c["key"] for c in question["choices"]}
        if (
            not isinstance(checked, list)
            or any(k not in valid_keys for k in checked)
            or len(set(checked)) != len(checked)
        ):
            raise HTTPException(
                status_code=422,
                detail=f"checked must be distinct valid keys {sorted(valid_keys)}",
            )
    corrections = _corrections()
    copy_corrections = corrections.setdefault(copy_id, {})
    if checked:
        copy_corrections[qid] = checked
    else:
        copy_corrections.pop(qid, None)
    save_json(CORRECTIONS_FILE, corrections)
    return _copy_detail(copy_id)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
