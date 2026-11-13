"""FastAPI review UI: copy list, annotated detail, manual corrections."""

import json
from pathlib import Path

from fastapi import FastAPI

app = FastAPI(title="mini-amc review")

DATA = Path(__file__).resolve().parents[3] / "data"


def load_json(name: str):
    """
    Load a JSON file from ``data/``.

    Args:
        name: File name (e.g. ``omr_results.json``).

    Returns:
        Decoded JSON content.
    """
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@app.get("/copies")
def list_copies() -> dict:
    """
    List the copies with their review status.

    Statuses: ``ok`` / ``needs_review`` / ``partial`` / ``unread``.

    Returns:
        Dict copy_id -> status and pages read (D7).

    Raises:
        NotImplementedError: Until D7 is implemented.
    """
    raise NotImplementedError("D7: list copies + status (ok / needs_review / unread)")


@app.get("/copy/{copy_id}")
def copy_detail(copy_id: str) -> dict:
    """
    Copy detail: annotated scan, detected choices, ongoing corrections.

    Args:
        copy_id: Copy identifier (e.g. ``0001``).

    Returns:
        Dict with questions, OMR answers and annotated scan path (D7).

    Raises:
        NotImplementedError: Until D7 is implemented.
    """
    raise NotImplementedError("D7: annotated scan + detected choices + corrections")


@app.post("/copy/{copy_id}/correction")
def post_correction(copy_id: str, payload: dict) -> dict:
    """
    Save a manual correction and recompute the copy's score.

    Args:
        copy_id: Copy identifier.
        payload: Correction (e.g. ``{"qid": "q1", "checked": ["B"]}``).

    Returns:
        The updated copy with its recomputed score (D7).

    Raises:
        NotImplementedError: Until D7 is implemented.
    """
    raise NotImplementedError("D7: save manual correction, recompute score")
