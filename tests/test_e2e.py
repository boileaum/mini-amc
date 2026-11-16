import csv
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
import qrcode
import yaml
from synth import (
    CORNER_PX,
    MARKER_PX,
    QR_PX,
    QR_X0,
    QR_Y0,
    H,
    W,
    _warp_photo,
    bubble_center,
)

from mini_amc.gen.generate import main as gen_main
from mini_amc.grade.notes import main as grades_main
from mini_amc.omr.read_scans import (
    BUBBLE_DX_PT,
    BUBBLE_DY_PT,
    BUBBLE_R_PT,
    SCALE,
    SQUARE_SIZE_PT,
)
from mini_amc.omr.read_scans import (
    main as omr_main,
)

N_COPIES = 30
N_QUESTIONS = 40
N_OPEN = 2
SEED = 7
TEMPLATE = Path("template")
SCORE_MAX = (N_QUESTIONS - N_OPEN) * 1 + 2 + 3


def _write_bank(path: Path) -> None:
    questions: list[dict] = [
        {
            "id": f"q{i}",
            "text": f"Question number {i}?",
            "choices": [
                # i=1,2 are multi-answer (square bubbles): two correct choices
                {
                    "text": f"choice {j}",
                    "correct": j == i % 3 or (i in (1, 2) and j == (i % 3 + 1) % 3),
                }
                for j in range(3)
            ],
        }
        for i in range(1, N_QUESTIONS - N_OPEN + 1)
    ]
    questions.append(
        {"id": "q39", "text": "Open question 39?", "type": "open", "max_points": 2}
    )
    questions.append(
        {"id": "q40", "text": "Open question 40?", "type": "open", "max_points": 3}
    )
    path.write_text(
        yaml.dump(
            {
                "meta": {"title": "E2E", "course": "E2E 101", "date": "2026-11-13"},
                "questions": questions,
            }
        ),
        encoding="utf-8",
    )


def _page_image(copy_id: str, page: int, copy_pos: dict, answers: dict):
    img = np.full((H, W, 3), 255, dtype=np.uint8)
    for cx, cy in (
        (CORNER_PX, CORNER_PX),
        (W - CORNER_PX - MARKER_PX, CORNER_PX),
        (CORNER_PX, H - CORNER_PX - MARKER_PX),
        (W - CORNER_PX - MARKER_PX, H - CORNER_PX - MARKER_PX),
    ):
        cv2.rectangle(img, (cx, cy), (cx + MARKER_PX, cy + MARKER_PX), (0, 0, 0), -1)
    qr = qrcode.make(f"copy:{copy_id}|page:{page}").convert("L")
    qr_img = np.array(qr.resize((QR_PX, QR_PX), qrcode.constants.ERROR_CORRECT_M))
    img[QR_Y0 : QR_Y0 + QR_PX, QR_X0 : QR_X0 + QR_PX] = cv2.cvtColor(
        qr_img, cv2.COLOR_GRAY2BGR
    )
    for b in copy_pos["bubbles"]:
        if b["page"] != page:
            continue
        cx, cy = bubble_center(b)
        if b.get("shape") == "square":
            half = int(SQUARE_SIZE_PT * SCALE / 2)
            cv2.rectangle(
                img,
                (cx - half, cy - half),
                (cx + half, cy + half),
                (0, 0, 0),
                max(1, int(SCALE)),
            )
            if b["key"] in (answers.get(b["qid"]) or []):
                cv2.rectangle(
                    img, (cx - half, cy - half), (cx + half, cy + half), (0, 0, 0), -1
                )
        else:
            cv2.circle(
                img, (cx, cy), int(BUBBLE_R_PT * SCALE), (0, 0, 0), max(1, int(SCALE))
            )
            if b["key"] in (answers.get(b["qid"]) or []):
                cv2.circle(img, (cx, cy), int(3.2 * SCALE), (0, 0, 0), -1)
    gradeboxes = copy_pos.get("gradeboxes", [])
    for g in gradeboxes:
        if g["page"] != page:
            continue
        cx = int((g["x_pt"] + BUBBLE_DX_PT) * SCALE)
        cy = int((g["y_pt"] + BUBBLE_DY_PT) * SCALE)
        cv2.circle(
            img, (cx, cy), int(BUBBLE_R_PT * SCALE), (0, 0, 0), max(1, int(SCALE))
        )
        qmax = max(gb["value"] for gb in gradeboxes if gb["qid"] == g["qid"])
        if g["value"] == qmax:
            cv2.circle(img, (cx, cy), int(3.2 * SCALE), (0, 0, 0), -1)
    return img


def _degraded_scan(img, out_jpg: Path, seed: int) -> None:
    tmp = out_jpg.with_suffix(".png")
    _warp_photo(img, tmp, seed=seed, jitter=30, margin=100)
    photo = cv2.imread(str(tmp))
    assert photo is not None
    tmp.unlink()
    rng = np.random.default_rng(seed + 1000)
    photo = np.clip(
        photo.astype(np.int16) + rng.normal(0, 8, photo.shape), 0, 255
    ).astype(np.uint8)
    cv2.imwrite(str(out_jpg), photo, [cv2.IMWRITE_JPEG_QUALITY, 80])


@pytest.fixture(scope="module")
def pipeline(tmp_path_factory):
    root = tmp_path_factory.mktemp("e2e")
    bank = root / "bank.yml"
    _write_bank(bank)
    data = root / "data"
    scans = root / "scans"
    scans.mkdir()
    with pytest.MonkeyPatch.context() as m:
        m.setattr(
            "sys.argv",
            [
                "mini-amc-gen",
                "--bank",
                str(bank),
                "--copies",
                str(N_COPIES),
                "--seed",
                str(SEED),
                "--template",
                str(TEMPLATE),
                "--out",
                str(data),
            ],
        )
        gen_main()
    positions = json.loads((data / "positions.json").read_text(encoding="utf-8"))
    answers = json.loads((data / "answers.json").read_text(encoding="utf-8"))
    assert (
        set(positions) == set(answers) == {f"{i:04d}" for i in range(1, N_COPIES + 1)}
    )
    assert len(list(data.glob("copy_*.pdf"))) == N_COPIES
    n_scans = 0
    for cid in sorted(positions):
        expected_pages = sorted({b["page"] for b in positions[cid]["bubbles"]})
        for page in expected_pages:
            img = _page_image(cid, page, positions[cid], answers[cid])
            if int(cid) % 5 == 0 and page == 2:
                img = np.rot90(img, 1).copy()
            _degraded_scan(img, scans / f"{cid}_p{page}.jpg", seed=n_scans)
            n_scans += 1
    with pytest.MonkeyPatch.context() as m:
        m.setattr(
            "sys.argv",
            [
                "mini-amc-omr",
                "--scans",
                str(scans),
                "--data",
                str(data),
            ],
        )
        omr_main()
    results = json.loads((data / "omr_results.json").read_text(encoding="utf-8"))
    with pytest.MonkeyPatch.context() as m:
        m.setattr("sys.argv", ["mini-amc-grades", "--data", str(data)])
        grades_main()
    copies_meta = {
        cid: json.loads((data / f"copy_{cid}.json").read_text(encoding="utf-8"))
        for cid in positions
    }
    return {
        "root": root,
        "data": data,
        "positions": positions,
        "answers": answers,
        "results": results,
        "copies_meta": copies_meta,
        "n_scans": n_scans,
    }


def test_e2e_generation(pipeline):
    assert pipeline["n_scans"] > N_COPIES
    for cid in pipeline["positions"]:
        copy_pos = pipeline["positions"][cid]
        pages = sorted({b["page"] for b in copy_pos["bubbles"]})
        assert pages, cid
        qids = {b["qid"] for b in copy_pos["bubbles"]} | {
            g["qid"] for g in copy_pos.get("gradeboxes", [])
        }
        assert len(qids) == N_QUESTIONS


def test_e2e_omr_all_copies_ok(pipeline):
    copies = pipeline["results"]["copies"]
    assert set(copies) == set(pipeline["answers"])
    for cid, c in copies.items():
        assert c["status"] == "ok", (cid, c["status"])
        read = {q["qid"]: q["checked"] for q in c["questions"]}
        assert len(read) == N_QUESTIONS
        for qid, expected in pipeline["answers"][cid].items():
            if expected == "open":
                mp = next(
                    q["max_points"]
                    for q in pipeline["copies_meta"][cid]["questions"]
                    if q["id"] == qid
                )
                assert read[qid] == [mp], (cid, qid, read[qid], mp)
            else:
                assert sorted(read[qid]) == sorted(expected), (
                    cid,
                    qid,
                    read[qid],
                    expected,
                )


def test_e2e_grades(pipeline):
    with (pipeline["data"] / "notes.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == N_COPIES
    for r in rows:
        assert r["status"] == "ok"
        assert r["score"] == r["score_max"] == str(SCORE_MAX)
    with (pipeline["data"] / "notes_detail.csv").open(
        encoding="utf-8", newline=""
    ) as f:
        detail = list(csv.DictReader(f))
    assert len(detail) == N_COPIES * N_QUESTIONS
    assert all(r["point"] != "0" for r in detail)
    assert {r["type"] for r in detail} == {"mcq", "open"}
    assert all(r["point"] in ("2", "3") for r in detail if r["type"] == "open")


def test_e2e_web_and_correction(pipeline, monkeypatch):
    from fastapi.testclient import TestClient

    from mini_amc.web import app as web_app

    monkeypatch.setattr(web_app, "DATA", pipeline["data"])
    client = TestClient(web_app.app)
    r = client.get("/copies")
    assert r.status_code == 200
    copies = r.json()["copies"]
    assert len(copies) == N_COPIES
    assert all(c["status"] == "ok" for c in copies)
    r = client.get("/copy/0001")
    assert r.json()["score"] == SCORE_MAX
    qid = next(q for q, v in pipeline["answers"]["0001"].items() if v != "open")
    wrong = next(k for k in "ABC" if k not in pipeline["answers"]["0001"][qid])
    r = client.post("/copy/0001/correction", json={"qid": qid, "checked": [wrong]})
    assert r.status_code == 200
    assert r.json()["score"] == SCORE_MAX - 1
    with pytest.MonkeyPatch.context() as m:
        m.setattr("sys.argv", ["mini-amc-grades", "--data", str(pipeline["data"])])
        grades_main()
    with (pipeline["data"] / "notes.csv").open(encoding="utf-8", newline="") as f:
        rows = {r["copy_id"]: r for r in csv.DictReader(f)}
    assert rows["0001"]["score"] == str(SCORE_MAX - 1)
    assert rows["0002"]["score"] == str(SCORE_MAX)
