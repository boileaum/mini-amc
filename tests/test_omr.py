import json
from pathlib import Path

import cv2
import numpy as np
import pytest
import qrcode

from mini_amc.omr.read_scans import (
    BUBBLE_DX_PT,
    BUBBLE_DY_PT,
    BUBBLE_R_PT,
    PAGE_H_PT,
    PAGE_W_PT,
    SCALE,
    detect_markers,
    process_scan,
    read_bubbles,
    read_qr,
    unwarp,
)

W = round(PAGE_W_PT * SCALE)
H = round(PAGE_H_PT * SCALE)
MARKER_PX = round(1.2 * 72 / 2.54 * SCALE)
CORNER_PX = round(0.7 * 72 / 2.54 * SCALE)
QR_PX = round(3.0 * 72 / 2.54 * SCALE)


def _bubble_pos(qid, key, idx, page=1):
    return {
        "qid": qid,
        "key": key,
        "page": page,
        "x_pt": 100.0,
        "y_pt": 200.0 + 22.0 * idx,
    }


def _draw_bubble(img, b, filled=False):
    cx = int((b["x_pt"] + BUBBLE_DX_PT) * SCALE)
    cy = int((b["y_pt"] + BUBBLE_DY_PT) * SCALE)
    r = int(BUBBLE_R_PT * SCALE)
    if filled:
        cv2.circle(img, (cx, cy), int(3.2 * SCALE), (0, 0, 0), -1)
    cv2.circle(img, (cx, cy), r, (0, 0, 0), max(1, int(SCALE)))


def _make_page(copy_id, page, answers):
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
    x0 = W - round(2.2 * 72 / 2.54 * SCALE) - QR_PX
    y0 = CORNER_PX
    img[y0 : y0 + QR_PX, x0 : x0 + QR_PX] = cv2.cvtColor(qr_img, cv2.COLOR_GRAY2BGR)
    bubbles = []
    idx = 0
    for qid, keys in (("q1", "ABC"), ("q2", "ABC")):
        for key in keys:
            b = _bubble_pos(qid, key, idx, page)
            _draw_bubble(img, b, filled=(answers.get(qid) == key))
            bubbles.append(b)
            idx += 1
    positions = {
        copy_id: {
            "copy_id": copy_id,
            "page": {"w_pt": round(PAGE_W_PT, 2), "h_pt": round(PAGE_H_PT, 2)},
            "questions": [],
            "bubbles": bubbles,
        }
    }
    return img, positions


def _warp_photo(img, out_path, seed=1):
    rng = np.random.default_rng(seed)
    src = np.array([[0, 0], [W, 0], [W, H], [0, H]], dtype=np.float32)
    dst = src + rng.uniform(-40, 40, src.shape).astype(np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    photo = cv2.warpPerspective(img, M, (W + 120, H + 120))
    cv2.imwrite(str(out_path), photo)
    return out_path


def test_detect_markers_synthetic():
    img, _ = _make_page("0007", 1, {})
    markers = detect_markers(img)
    assert markers.shape == (4, 2)
    expected = np.array(
        [
            [CORNER_PX + MARKER_PX / 2, CORNER_PX + MARKER_PX / 2],
            [W - CORNER_PX - MARKER_PX / 2, CORNER_PX + MARKER_PX / 2],
            [W - CORNER_PX - MARKER_PX / 2, H - CORNER_PX - MARKER_PX / 2],
            [CORNER_PX + MARKER_PX / 2, H - CORNER_PX - MARKER_PX / 2],
        ]
    )
    assert np.allclose(markers, expected, atol=4)


def test_detect_markers_rejects_incomplete():
    img = np.full((H, W, 3), 255, dtype=np.uint8)
    cv2.rectangle(
        img,
        (CORNER_PX, CORNER_PX),
        (CORNER_PX + MARKER_PX, CORNER_PX + MARKER_PX),
        (0, 0, 0),
        -1,
    )
    with pytest.raises(ValueError, match="markers"):
        detect_markers(img)


def test_unwarp_dimensions():
    img, _ = _make_page("0007", 1, {})
    markers = detect_markers(img)
    warped = unwarp(img, markers)
    assert warped.shape == (H, W, 3)


def test_read_qr():
    img, _ = _make_page("0007", 3, {})
    markers = detect_markers(img)
    warped = unwarp(img, markers)
    assert read_qr(warped) == {"copy_id": "0007", "page": 3, "rot": 0}


def test_read_bubbles_filled_empty_ambiguous():
    img, positions = _make_page("0001", 1, {"q1": "B", "q2": "A"})
    warped = unwarp(img, detect_markers(img))
    questions = read_bubbles(warped, positions["0001"], 1)
    assert {q["qid"]: q["checked"] for q in questions} == {"q1": ["B"], "q2": ["A"]}
    assert all(not q["needs_review"] for q in questions)
    assert questions[0]["fills"]["B"] > 0.8
    assert questions[0]["fills"]["A"] < 0.2

    img2, positions2 = _make_page("0001", 1, {})
    q2 = read_bubbles(unwarp(img2, detect_markers(img2)), positions2["0001"], 1)
    assert all(q["checked"] == [] and not q["needs_review"] for q in q2)

    img_gris, positions_gris = _make_page("0001", 1, {})
    b = _bubble_pos("q1", "A", 0, 1)
    cx = int((b["x_pt"] + BUBBLE_DX_PT) * SCALE)
    cy = int((b["y_pt"] + BUBBLE_DY_PT) * SCALE)
    cv2.circle(img_gris, (cx, cy), int(1.2 * SCALE), (0, 0, 0), -1)
    qg = read_bubbles(
        unwarp(img_gris, detect_markers(img_gris)), positions_gris["0001"], 1
    )
    assert qg[0]["checked"] == [] and qg[0]["needs_review"]

    img3, positions3 = _make_page("0001", 1, {"q1": "A"})
    _draw_bubble(img3, _bubble_pos("q1", "C", 2, 1), filled=True)
    q3 = read_bubbles(unwarp(img3, detect_markers(img3)), positions3["0001"], 1)
    assert q3[0]["needs_review"] and set(q3[0]["checked"]) == {"A", "C"}


def test_process_scan_warped_photo(tmp_path):
    img, positions = _make_page("0042", 2, {"q1": "C", "q2": "B"})
    scan = _warp_photo(img, tmp_path / "scan_0042_p2.png", seed=3)
    result = process_scan(scan, positions, tmp_path / "annotated")
    assert result["status"] == "ok", result["error"]
    assert result["copy_id"] == "0042"
    assert result["page"] == 2
    assert {q["qid"]: q["checked"] for q in result["questions"]} == {
        "q1": ["C"],
        "q2": ["B"],
    }
    assert result["annotated"] and Path(result["annotated"]).exists()


def test_process_scan_unread(tmp_path):
    img = np.full((H, W, 3), 255, dtype=np.uint8)
    cv2.imwrite(str(tmp_path / "blank.png"), img)
    result = process_scan(tmp_path / "blank.png", {})
    assert result["status"] == "unread"
    assert result["error"]


def test_main_end_to_end(tmp_path, monkeypatch):
    from mini_amc.omr.read_scans import main

    scans = tmp_path / "scans"
    scans.mkdir()
    img_ok, positions = _make_page("0001", 1, {"q1": "A", "q2": "C"})
    _warp_photo(img_ok, scans / "scan_0001_p1.png", seed=5)
    img_bad, _ = _make_page("0002", 1, {"q1": "A", "q2": "B"})
    _warp_photo(img_bad, scans / "scan_0002_p1.png", seed=6)
    positions["0002"] = _make_page("0002", 1, {})[1]["0002"]
    (tmp_path / "positions.json").write_text(json.dumps(positions), encoding="utf-8")
    cv2.imwrite(str(scans / "blank.png"), np.full((H, W, 3), 255, dtype=np.uint8))
    monkeypatch.setattr(
        "sys.argv",
        [
            "mini-amc-omr",
            "--scans",
            str(scans),
            "--positions",
            str(tmp_path / "positions.json"),
            "--out",
            str(tmp_path / "omr_results.json"),
            "--annotated",
            str(tmp_path / "annotated"),
        ],
    )
    main()
    results = json.loads((tmp_path / "omr_results.json").read_text())
    assert results["scans"]["scan_0001_p1.png"]["status"] == "ok"
    assert results["scans"]["scan_0001_p1.png"]["copy_id"] == "0001"
    assert results["scans"]["blank.png"]["status"] == "unread"
    assert results["copies"]["0001"]["status"] == "ok"
    assert results["copies"]["0001"]["pages"] == [1]
    assert len(results["copies"]["0001"]["questions"]) == 2
    assert (tmp_path / "annotated" / "scan_0001_p1.png").exists()


def test_process_scan_rotated_page(tmp_path):
    img, positions = _make_page("0009", 1, {"q1": "B", "q2": "C"})
    img = np.rot90(img, 2).copy()
    scan = _warp_photo(img, tmp_path / "scan_0009_p1.png", seed=8)
    result = process_scan(scan, positions)
    assert result["status"] == "ok", result["error"]
    assert result["copy_id"] == "0009" and result["page"] == 1
    assert {q["qid"]: q["checked"] for q in result["questions"]} == {
        "q1": ["B"],
        "q2": ["C"],
    }


def test_main_multipage_and_partial(tmp_path, monkeypatch):
    from mini_amc.omr.read_scans import main

    scans = tmp_path / "scans"
    scans.mkdir()
    img1, pos1 = _make_page("0005", 1, {"q1": "A", "q2": "B"})
    img2, pos2 = _make_page("0005", 2, {"q1": "C", "q2": "A"})
    positions = {
        "0005": {
            "copy_id": "0005",
            "page": pos1["0005"]["page"],
            "questions": [],
            "bubbles": pos1["0005"]["bubbles"] + pos2["0005"]["bubbles"],
        }
    }
    _warp_photo(img1, scans / "scan_0005_p1.png", seed=21)
    _warp_photo(img2, scans / "scan_0005_p2.png", seed=22)
    (tmp_path / "positions.json").write_text(json.dumps(positions), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "mini-amc-omr",
            "--scans",
            str(scans),
            "--positions",
            str(tmp_path / "positions.json"),
            "--out",
            str(tmp_path / "omr_results.json"),
            "--annotated",
            str(tmp_path / "annotated"),
        ],
    )
    main()
    results = json.loads((tmp_path / "omr_results.json").read_text())
    copy = results["copies"]["0005"]
    assert copy["status"] == "ok"
    assert copy["pages"] == [1, 2]
    assert len(copy["questions"]) == 4
    assert {q["qid"] + f"@p{q['page']}" for q in copy["questions"]} == {
        "q1@p1",
        "q2@p1",
        "q1@p2",
        "q2@p2",
    }
    by_key = {f"{q['qid']}@p{q['page']}": q["checked"] for q in copy["questions"]}
    assert by_key["q1@p1"] == ["A"] and by_key["q2@p2"] == ["A"]

    (scans / "scan_0005_p2.png").unlink()
    main()
    results = json.loads((tmp_path / "omr_results.json").read_text())
    assert results["copies"]["0005"]["status"] == "partial"
