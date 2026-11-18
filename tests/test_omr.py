import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from synth import (
    CORNER_PX,
    MARKER_PX,
    SCALE,
    H,
    W,
    _bubble_pos,
    _draw_bubble,
    _make_page,
    _save_pdf,
    _warp_photo,
)

from mini_amc.omr.read_scans import (
    BUBBLE_DX_PT,
    BUBBLE_DY_PT,
    detect_markers,
    process_scan,
    read_bubbles,
    read_qr,
    unwarp,
)


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
            "--data",
            str(tmp_path),
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
            "--data",
            str(tmp_path),
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


def test_main_missing_scans_dir(tmp_path, monkeypatch):
    from mini_amc.omr.read_scans import main

    (tmp_path / "positions.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "mini-amc-omr",
            "--scans",
            str(tmp_path / "nope"),
            "--data",
            str(tmp_path),
        ],
    )
    with pytest.raises(SystemExit):
        main()


def test_main_missing_positions(tmp_path, monkeypatch):
    from mini_amc.omr.read_scans import main

    scans = tmp_path / "scans"
    scans.mkdir()
    monkeypatch.setattr(
        "sys.argv",
        [
            "mini-amc-omr",
            "--scans",
            str(scans),
            "--data",
            str(tmp_path),
        ],
    )
    with pytest.raises(SystemExit):
        main()


def test_read_bubbles_open_gradeboxes():
    from synth import H, W, _draw_bubble

    from mini_amc.omr.read_scans import read_bubbles

    def make(filled_values):
        boxes = [
            {
                "qid": "q9",
                "value": v,
                "page": 1,
                "x_pt": 100.0,
                "y_pt": 200.0 + 22.0 * v,
            }
            for v in range(3)
        ]
        img = np.full((H, W, 3), 255, dtype=np.uint8)
        for b in boxes:
            _draw_bubble(img, b, filled=(b["value"] in filled_values))
        pos = {
            "page": {"w_pt": 595.28, "h_pt": 841.89},
            "questions": [],
            "bubbles": [],
            "gradeboxes": boxes,
        }
        return read_bubbles(img, pos, 1)

    q = make({1})[0]
    assert q["type"] == "open"
    assert q["checked"] == [1]
    assert q["needs_review"] is False
    assert q["fills"]["1"] > 0.35
    assert q["fills"]["0"] < 0.15
    blank = make(set())[0]
    assert blank["checked"] == [] and blank["needs_review"] is True
    double = make({0, 2})[0]
    assert double["checked"] == [0, 2] and double["needs_review"] is True


def test_aggregate_copies_gradebox_only_page():
    from mini_amc.omr.read_scans import aggregate_copies

    positions = {
        "0009": {
            "bubbles": [{"qid": "q1", "key": "A", "page": 1, "x_pt": 0.0, "y_pt": 0.0}],
            "gradeboxes": [
                {"qid": "q9", "value": v, "page": 2, "x_pt": 0.0, "y_pt": 0.0}
                for v in range(2)
            ],
        }
    }
    results = {
        "s1.png": {
            "scan": "s1.png",
            "status": "ok",
            "copy_id": "0009",
            "page": 1,
            "questions": [
                {
                    "qid": "q1",
                    "type": "mcq",
                    "fills": {"A": 0.9},
                    "checked": ["A"],
                    "needs_review": False,
                }
            ],
            "annotated": None,
            "error": None,
        },
        "s2.png": {
            "scan": "s2.png",
            "status": "ok",
            "copy_id": "0009",
            "page": 2,
            "questions": [
                {
                    "qid": "q9",
                    "type": "open",
                    "fills": {"1": 0.9},
                    "checked": [1],
                    "needs_review": False,
                }
            ],
            "annotated": None,
            "error": None,
        },
    }
    copies = aggregate_copies(results, positions)
    assert copies["0009"]["status"] == "ok"
    assert copies["0009"]["pages"] == [1, 2]


def test_read_bubbles_multi_answer_squares():
    from synth import _draw_bubble

    from mini_amc.omr.read_scans import read_bubbles

    bubbles = [
        _bubble_pos("qm", k, i, shape="square", multi=True) for i, k in enumerate("ABC")
    ]
    img = np.full((H, W, 3), 255, dtype=np.uint8)
    _draw_bubble(img, bubbles[0], filled=True)
    _draw_bubble(img, bubbles[2], filled=True)
    pos = {
        "page": {"w_pt": 595.28, "h_pt": 841.89},
        "questions": [],
        "bubbles": bubbles,
    }
    q = read_bubbles(img, pos, 1)[0]
    assert q["multi"] is True
    assert q["checked"] == ["A", "C"]
    assert q["needs_review"] is False

    # same but single-answer (circle): two checked = needs_review
    bubbles1 = [_bubble_pos("q1", k, i) for i, k in enumerate("ABC")]
    img1 = np.full((H, W, 3), 255, dtype=np.uint8)
    _draw_bubble(img1, bubbles1[0], filled=True)
    _draw_bubble(img1, bubbles1[1], filled=True)
    pos1 = {
        "page": {"w_pt": 595.28, "h_pt": 841.89},
        "questions": [],
        "bubbles": bubbles1,
    }
    q1 = read_bubbles(img1, pos1, 1)[0]
    assert q1["checked"] == ["A", "B"] and q1["needs_review"] is True


def test_process_scan_pdf_page(tmp_path):
    img, positions = _make_page("0042", 2, {"q1": "C", "q2": "B"})
    pdf = _save_pdf([img], tmp_path / "batch.pdf")
    result = process_scan(pdf, positions, tmp_path / "annotated")
    assert result["status"] == "ok", result["error"]
    assert result["scan"] == "batch.pdf"
    assert result["file_page"] == 1
    assert result["copy_id"] == "0042" and result["page"] == 2
    assert {q["qid"]: q["checked"] for q in result["questions"]} == {
        "q1": ["C"],
        "q2": ["B"],
    }
    assert Path(result["annotated"]).name == "batch_p1.png"


def test_main_multipage_pdf(tmp_path, monkeypatch):
    from mini_amc.omr.read_scans import main

    scans = tmp_path / "scans"
    scans.mkdir()
    img1, pos1 = _make_page("0011", 1, {"q1": "A", "q2": "B"})
    img2, pos2 = _make_page("0012", 1, {"q1": "C", "q2": "A"})
    _save_pdf([img1, img2], scans / "batch.pdf")
    (tmp_path / "positions.json").write_text(
        json.dumps({**pos1, **pos2}), encoding="utf-8"
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "mini-amc-omr",
            "--scans",
            str(scans),
            "--data",
            str(tmp_path),
            "--pdf-dpi",
            "200",
        ],
    )
    main()
    results = json.loads((tmp_path / "omr_results.json").read_text())
    assert set(results["scans"]) == {"batch.pdf#p1", "batch.pdf#p2"}
    assert results["scans"]["batch.pdf#p1"]["copy_id"] == "0011"
    assert results["scans"]["batch.pdf#p2"]["copy_id"] == "0012"
    assert results["copies"]["0011"]["status"] == "ok"
    assert results["copies"]["0012"]["status"] == "ok"
    assert (tmp_path / "annotated" / "batch_p1.png").exists()
    assert (tmp_path / "annotated" / "batch_p2.png").exists()


def test_main_corrupt_pdf(tmp_path, monkeypatch):
    from mini_amc.omr.read_scans import main

    scans = tmp_path / "scans"
    scans.mkdir()
    (scans / "broken.pdf").write_text("not a pdf", encoding="utf-8")
    (tmp_path / "positions.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        ["mini-amc-omr", "--scans", str(scans), "--data", str(tmp_path)],
    )
    main()
    results = json.loads((tmp_path / "omr_results.json").read_text())
    assert results["scans"]["broken.pdf#p1"]["status"] == "unread"
    assert results["scans"]["broken.pdf#p1"]["error"]
