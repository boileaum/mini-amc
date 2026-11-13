import json

import cv2
import numpy as np
from synth import QR_PX, QR_X0, QR_Y0, _make_page, _warp_photo

from mini_amc.omr.read_scans import process_scan

ANSWERS = {"q1": "B", "q2": "C"}


def _scan(tmp_path, name, degrade=None, seed=7):
    img, positions = _make_page("0077", 1, ANSWERS)
    f = 1.0
    if degrade == "lowdpi":
        f = 0.5
    if degrade == "verylowdpi":
        f = 0.35
    if f < 1.0:
        img = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    if degrade == "qr_damaged":
        cv2.rectangle(
            img,
            (QR_X0 + QR_PX // 2, QR_Y0),
            (QR_X0 + QR_PX, QR_Y0 + QR_PX),
            (255, 255, 255),
            -1,
        )
    path = tmp_path / name
    _warp_photo(img, path, seed=seed, jitter=int(40 * f) + 4, margin=int(120 * f) + 20)
    photo = cv2.imread(str(path))
    assert photo is not None
    if degrade == "noise":
        rng = np.random.default_rng(3)
        photo = np.clip(
            photo.astype(np.int16) + rng.normal(0, 20, photo.shape), 0, 255
        ).astype(np.uint8)
    elif degrade == "dark":
        photo = (photo.astype(np.float32) * 0.55).astype(np.uint8)
    elif degrade == "bright":
        photo = np.clip(photo.astype(np.float32) * 1.4 + 20, 0, 255).astype(np.uint8)
    elif degrade == "blur":
        photo = cv2.GaussianBlur(photo, (5, 5), 0)
    elif degrade == "jpeg":
        path = path.with_suffix(".jpg")
        cv2.imwrite(str(path), photo, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return path, positions
    elif degrade == "marker_cut":
        photo = photo[:, 60:]
    elif degrade == "sideways":
        photo = np.rot90(photo, 1).copy()
    cv2.imwrite(str(path), photo)
    return path, positions


def _assert_ok(result, answers=ANSWERS):
    assert result["status"] == "ok", result["error"]
    assert result["copy_id"] == "0077" and result["page"] == 1
    got = {q["qid"]: q["checked"] for q in result["questions"]}
    assert got == {qid: [key] for qid, key in answers.items()}


def test_noise(tmp_path):
    path, positions = _scan(tmp_path, "noise.png", "noise")
    _assert_ok(process_scan(path, positions))


def test_underexposed(tmp_path):
    path, positions = _scan(tmp_path, "dark.png", "dark")
    _assert_ok(process_scan(path, positions))


def test_overexposed(tmp_path):
    path, positions = _scan(tmp_path, "bright.png", "bright")
    _assert_ok(process_scan(path, positions))


def test_blur(tmp_path):
    path, positions = _scan(tmp_path, "blur.png", "blur")
    _assert_ok(process_scan(path, positions))


def test_low_dpi(tmp_path):
    path, positions = _scan(tmp_path, "lowdpi.png", "lowdpi")
    _assert_ok(process_scan(path, positions))


def test_very_low_dpi(tmp_path):
    path, positions = _scan(tmp_path, "verylowdpi.png", "verylowdpi")
    _assert_ok(process_scan(path, positions))


def test_jpeg_compression(tmp_path):
    path, positions = _scan(tmp_path, "scan.jpg", "jpeg")
    _assert_ok(process_scan(path, positions))


def test_sideways_page(tmp_path):
    path, positions = _scan(tmp_path, "sideways.png", "sideways")
    _assert_ok(process_scan(path, positions))


def test_marker_cut_is_unread_not_crash(tmp_path):
    path, positions = _scan(tmp_path, "cut.png", "marker_cut")
    result = process_scan(path, positions)
    assert result["status"] == "unread"
    assert "markers" in result["error"]


def test_damaged_qr_is_unread_not_crash(tmp_path):
    path, positions = _scan(tmp_path, "qrdead.png", "qr_damaged")
    result = process_scan(path, positions)
    assert result["status"] == "unread"
    assert result["error"]


def test_batch_mixed_statuses(tmp_path, monkeypatch):
    from mini_amc.omr.read_scans import main

    scans = tmp_path / "scans"
    scans.mkdir()
    positions = {}
    img, pos = _make_page("0001", 1, {"q1": "A", "q2": "B"})
    _warp_photo(img, scans / "a.png", seed=1)
    positions.update(pos)
    img, pos = _make_page("0002", 1, {"q1": "A"})
    from synth import _bubble_pos, _draw_bubble

    _draw_bubble(img, _bubble_pos("q1", "B", 1, 1), filled=True)
    _warp_photo(img, scans / "b.png", seed=2)
    positions.update(pos)
    cv2.imwrite(str(scans / "c.png"), np.full((2000, 1500, 3), 255, np.uint8))
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
    assert results["copies"]["0001"]["status"] == "ok"
    assert results["copies"]["0002"]["status"] == "needs_review"
    assert results["scans"]["c.png"]["status"] == "unread"
