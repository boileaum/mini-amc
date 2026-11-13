import json

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from mini_amc.web import app as web_app


def _bubble(qid, key, page):
    return {"qid": qid, "key": key, "page": page, "x_pt": 100.0, "y_pt": 200.0}


@pytest.fixture()
def data_dir(tmp_path):
    data = tmp_path / "data"
    (data / "annotated").mkdir(parents=True)
    (tmp_path / "scans").mkdir()
    positions = {
        "0001": {
            "bubbles": [_bubble("q1", k, 1) for k in "ABC"]
            + [_bubble("q2", k, 2) for k in "ABC"]
        },
        "0002": {"bubbles": [_bubble("q1", k, 1) for k in "ABC"]},
    }
    (data / "positions.json").write_text(json.dumps(positions), encoding="utf-8")
    (data / "answers.json").write_text(
        json.dumps({"0001": {"q1": "B", "q2": "A"}}), encoding="utf-8"
    )
    copy = {
        "copy_id": "0001",
        "meta": {"title": "Demo", "course": "Demo 101", "date": "2026-11-12"},
        "questions": [
            {
                "id": "q1",
                "text": "Capital of France?",
                "choices": [
                    {"key": "A", "text": "Lyon", "correct": False},
                    {"key": "B", "text": "Paris", "correct": True},
                    {"key": "C", "text": "Marseille", "correct": False},
                ],
            },
            {
                "id": "q2",
                "text": "7 x 8?",
                "choices": [
                    {"key": "A", "text": "56", "correct": True},
                    {"key": "B", "text": "54", "correct": False},
                    {"key": "C", "text": "63", "correct": False},
                ],
            },
        ],
    }
    (data / "copy_0001.json").write_text(json.dumps(copy), encoding="utf-8")
    q1 = {
        "qid": "q1",
        "fills": {"A": 0.9, "B": 0.8, "C": 0.01},
        "checked": ["A", "B"],
        "needs_review": True,
    }
    q2 = {
        "qid": "q2",
        "fills": {"A": 0.95, "B": 0.0, "C": 0.0},
        "checked": ["A"],
        "needs_review": False,
    }
    scans = {
        "s1.jpg": {
            "scan": "s1.jpg",
            "status": "needs_review",
            "copy_id": "0001",
            "page": 1,
            "questions": [dict(q1)],
            "annotated": "data/annotated/s1.jpg",
            "error": None,
        },
        "s2.jpg": {
            "scan": "s2.jpg",
            "status": "ok",
            "copy_id": "0001",
            "page": 2,
            "questions": [dict(q2)],
            "annotated": "data/annotated/s2.jpg",
            "error": None,
        },
        "bad.png": {
            "scan": "bad.png",
            "status": "unread",
            "copy_id": None,
            "page": None,
            "questions": [],
            "annotated": None,
            "error": "markers not found",
        },
    }
    omr = {
        "scans": scans,
        "copies": {
            "0001": {
                "pages": [1, 2],
                "questions": [dict(q1, page=1), dict(q2, page=2)],
                "status": "needs_review",
            }
        },
    }
    (data / "omr_results.json").write_text(json.dumps(omr), encoding="utf-8")
    img = np.full((10, 10, 3), 255, np.uint8)
    cv2.imwrite(str(data / "annotated" / "s1.jpg"), img)
    cv2.imwrite(str(data / "annotated" / "s2.jpg"), img)
    cv2.imwrite(str(tmp_path / "scans" / "s1.jpg"), img)
    return data


@pytest.fixture()
def client(data_dir, monkeypatch):
    monkeypatch.setattr(web_app, "DATA", data_dir)
    return TestClient(web_app.app)


def test_index(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "mini-amc review"


def test_list_copies(client):
    r = client.get("/copies")
    assert r.status_code == 200
    copies = {c["copy_id"]: c for c in r.json()["copies"]}
    assert copies["0001"]["status"] == "needs_review"
    assert copies["0001"]["pages"] == [1, 2]
    assert copies["0001"]["questions_read"] == 2
    assert copies["0001"]["questions_total"] == 2
    assert copies["0002"]["status"] == "unread"
    assert copies["0002"]["questions_read"] == 0


def test_copy_detail(client):
    r = client.get("/copy/0001")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "needs_review"
    assert body["scans"] == {"1": "s1.jpg", "2": "s2.jpg"}
    assert body["score"] == 1 and body["score_max"] == 2
    q1 = next(q for q in body["questions"] if q["qid"] == "q1")
    assert q1["checked"] == ["A", "B"]
    assert q1["needs_review"] is True
    assert q1["expected"] == "B"
    assert q1["correction"] is None
    assert q1["page"] == 1
    assert q1["choices"][1]["text"] == "Paris"


def test_copy_detail_unknown(client):
    assert client.get("/copy/9999").status_code == 404


def test_post_correction(client, data_dir):
    r = client.post("/copy/0001/correction", json={"qid": "q1", "checked": ["B"]})
    assert r.status_code == 200
    body = r.json()
    q1 = next(q for q in body["questions"] if q["qid"] == "q1")
    assert q1["correction"] == ["B"]
    assert body["score"] == 2
    assert body["corrected"] == 1
    saved = json.loads((data_dir / "corrections.json").read_text(encoding="utf-8"))
    assert saved == {"0001": {"q1": ["B"]}}
    r = client.get("/copy/0001")
    assert r.json()["score"] == 2


def test_post_correction_clear(client):
    client.post("/copy/0001/correction", json={"qid": "q1", "checked": ["B"]})
    r = client.post("/copy/0001/correction", json={"qid": "q1", "checked": []})
    assert r.status_code == 200
    q1 = next(q for q in r.json()["questions"] if q["qid"] == "q1")
    assert q1["correction"] is None
    assert r.json()["score"] == 1


def test_post_correction_invalid(client):
    assert (
        client.post(
            "/copy/0001/correction", json={"qid": "qX", "checked": ["A"]}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/copy/0001/correction", json={"qid": "q1", "checked": ["Z"]}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/copy/0001/correction", json={"qid": "q1", "checked": ["A", "A"]}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/copy/9999/correction", json={"qid": "q1", "checked": ["A"]}
        ).status_code
        == 404
    )


def test_copy_scan(client):
    r = client.get("/copy/0001/scan/1")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert client.get("/copy/0001/scan/9").status_code == 404
    assert client.get("/copy/0002/scan/1").status_code == 404


def test_empty_data(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "DATA", tmp_path / "data")
    c = TestClient(web_app.app)
    assert c.get("/copies").json() == {"copies": []}
    assert c.get("/copy/0001").status_code == 404
    assert (
        c.post(
            "/copy/0001/correction", json={"qid": "q1", "checked": ["A"]}
        ).status_code
        == 404
    )
