"""Local OMR reading of scanned answer sheets: markers, homography, QR, bubbles."""

import argparse
import json
import re
from pathlib import Path

import cv2
import numpy as np

from mini_amc.gen.generate import CM_TO_PT, PAGE_H_CM, PAGE_W_CM

PAGE_W_PT = PAGE_W_CM * CM_TO_PT
PAGE_H_PT = PAGE_H_CM * CM_TO_PT
SCALE = 2.0
MARKER_SIZE_CM = 1.2
CORNER_CM = 0.7
MARKER_CENTER_PT = (CORNER_CM + MARKER_SIZE_CM / 2) * CM_TO_PT
BUBBLE_R_PT = 4.5
BUBBLE_DX_PT = BUBBLE_R_PT
BUBBLE_DY_PT = 3.0
FILL_R_PT = 2.5
THRESHOLD = 0.35
GRAY_THRESHOLD = 0.15
QR_RE = re.compile(r"copy:(\d+)\|page:(\d+)")


def detect_markers(image: np.ndarray) -> np.ndarray:
    """
    Detect the 4 black alignment squares of a scanned page.

    Args:
        image: BGR image (any scan, perspective accepted).

    Returns:
        4x2 array of square centers, ordered top-left, top-right,
        bottom-right, bottom-left.

    Raises:
        ValueError: If the number of square candidates is not 4.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    n, _, stats, centroids = cv2.connectedComponentsWithStats(bw, connectivity=8)
    area = gray.shape[0] * gray.shape[1]
    cands = []
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        if not (0.0012 * area <= a <= 0.02 * area):
            continue
        fill = a / (w * h)
        aspect = w / h
        if fill < 0.7 or not (0.6 <= aspect <= 1.6):
            continue
        cands.append((float(centroids[i][0]), float(centroids[i][1])))
    if len(cands) < 4:
        raise ValueError(f"{len(cands)} markers found (4 required)")
    h, w = gray.shape
    max_d = 0.25 * max(h, w)
    chosen = []
    for cx, cy in ((0, 0), (w, 0), (w, h), (0, h)):
        best = min(cands, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
        if best in chosen or ((best[0] - cx) ** 2 + (best[1] - cy) ** 2) ** 0.5 > max_d:
            raise ValueError(f"no marker near corner ({cx}, {cy})")
        chosen.append(best)
    return np.array(chosen, dtype=np.float32)


def _dst_points(scale: float) -> np.ndarray:
    m = MARKER_CENTER_PT * scale
    w = PAGE_W_PT * scale
    h = PAGE_H_PT * scale
    return np.array([[m, m], [w - m, m], [w - m, h - m], [m, h - m]], dtype=np.float32)


def unwarp(image: np.ndarray, markers: np.ndarray, scale: float = SCALE) -> np.ndarray:
    """
    Straighten the page by homography to an A4 at ``scale`` px/pt.

    If the marker quadrilateral is wider than tall (page scanned
    sideways), the destination corners are cyclically shifted so the
    output stays a portrait A4 instead of being anisotropically
    stretched; :func:`read_qr` then fixes any residual 180° flip.

    Args:
        image: Page scan.
        markers: Centers of the 4 squares (:func:`detect_markers` order).
        scale: Output resolution in px/pt (2.0 ≈ 144 dpi).

    Returns:
        Straightened A4 image (white border outside the scanned area).
    """
    dst = _dst_points(scale)
    quad_w = (
        np.linalg.norm(markers[1] - markers[0])
        + np.linalg.norm(markers[2] - markers[3])
    ) / 2
    quad_h = (
        np.linalg.norm(markers[3] - markers[0])
        + np.linalg.norm(markers[2] - markers[1])
    ) / 2
    if quad_w > quad_h:
        dst = np.roll(dst, 1, axis=0)
    M = cv2.getPerspectiveTransform(markers, dst)
    return cv2.warpPerspective(
        image,
        M,
        (round(PAGE_W_PT * scale), round(PAGE_H_PT * scale)),
        borderValue=(255, 255, 255),
    )


def _decode_crops(img: np.ndarray, det) -> str | None:
    s = img.shape[1] / PAGE_W_PT
    h, w = img.shape[:2]
    crops = [
        img[0 : int(130 * s), int(340 * s) : min(w, int(470 * s))],
        img[0 : int(160 * s), int(300 * s) : w],
        img[0 : int(200 * s), 0:w],
        img,
    ]
    for crop in crops:
        for variant0 in (
            crop,
            cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC),
        ):
            gray = cv2.cvtColor(variant0, cv2.COLOR_BGR2GRAY)
            _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            for variant in (variant0, bw):
                ok, decoded, _, _ = det.detectAndDecodeMulti(variant)
                texts = list(decoded) if ok and decoded else []
                if not texts:
                    data, _, _ = det.detectAndDecode(variant)
                    if data:
                        texts = [data]
                for t in texts:
                    if QR_RE.fullmatch(t or ""):
                        return t
    return None


def read_qr(warped: np.ndarray) -> dict:
    """
    Read the QR code of a straightened page (content ``copy:XXXX|page:N``).

    Tries the 4 page orientations and keeps the one where the QR is
    detected at the top right (the expected position): the page may be
    scanned sideways or upside down, and the QR detector of some OpenCV
    builds does not localize 90°-rotated codes.

    Args:
        warped: Page straightened by :func:`unwarp` (any orientation).

    Returns:
        Dict with ``copy_id``, ``page`` and ``rot`` (rotation in degrees
        such that ``np.rot90(warped, -rot // 90)`` makes the page upright).

    Raises:
        ValueError: If no readable QR code is found.
    """
    det = cv2.QRCodeDetector()

    def parse(text: str, k: int) -> dict | None:
        m = QR_RE.fullmatch(text)
        if m is None:
            return None
        return {"copy_id": m.group(1), "page": int(m.group(2)), "rot": (-k * 90) % 360}

    fallback = None
    for k in range(4):
        img = np.rot90(warped, k) if k else warped
        h, w = img.shape[:2]
        text = _decode_crops(img, det)
        if not text:
            continue
        parsed = parse(text, k)
        if parsed is None:
            continue
        ok, points = det.detect(img)
        c = (
            points[0].mean(axis=0)
            if ok and points is not None and len(points) > 0
            else None
        )
        top_right = c is not None and c[0] > 0.55 * w and c[1] < 0.3 * h
        if top_right:
            return parsed
        if fallback is None:
            fallback = parsed
    if fallback is not None:
        return fallback
    raise ValueError("QR code unreadable")


def read_bubbles(
    warped: np.ndarray,
    copy_positions: dict,
    page: int,
    threshold: float = THRESHOLD,
    gray_threshold: float = GRAY_THRESHOLD,
) -> list[dict]:
    """
    Read the checked bubbles of a straightened page.

    For each bubble, measures the ink density of the inner disk
    (center = metadata + calibrated offset). A choice is checked if
    its fill >= ``threshold``; ``needs_review`` if several choices are
    checked or a gray trace exists (fill between ``gray_threshold`` and
    ``threshold``).

    Args:
        warped: Straightened and reoriented page.
        copy_positions: ``positions.json`` entry of one copy.
        page: Page number to read (bubbles of other pages are ignored).
        threshold: Fill threshold for a checked bubble.
        gray_threshold: Fill threshold for detecting a gray trace.

    Returns:
        List of questions (``qid``, ``fills`` per key, ``checked``,
        ``needs_review``), sorted by ``qid``.
    """
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    _, bw = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV)
    h, w = gray.shape
    s = w / PAGE_W_PT
    r = max(1, int(FILL_R_PT * s))
    questions: dict[str, dict] = {}
    for b in copy_positions["bubbles"]:
        if b["page"] != page:
            continue
        cx = int((b["x_pt"] + BUBBLE_DX_PT) * s)
        cy = int((b["y_pt"] + BUBBLE_DY_PT) * s)
        y0, y1 = max(0, cy - r), min(h, cy + r)
        x0, x1 = max(0, cx - r), min(w, cx + r)
        patch = bw[y0:y1, x0:x1]
        mask = np.zeros(patch.shape, dtype=np.uint8)
        cv2.circle(mask, (cx - x0, cy - y0), r, 255, -1)
        sel = patch[mask > 0]
        fill = float(sel.mean()) / 255 if sel.size else 0.0
        q = questions.setdefault(
            b["qid"], {"qid": b["qid"], "fills": {}, "checked": []}
        )
        q["fills"][b["key"]] = round(fill, 3)
    result = []
    for qid in sorted(questions):
        q = questions[qid]
        q["fills"] = dict(sorted(q["fills"].items()))
        checked = [k for k, f in q["fills"].items() if f >= threshold]
        gray_marks = [
            k for k, f in q["fills"].items() if gray_threshold <= f < threshold
        ]
        q["checked"] = checked
        q["needs_review"] = len(checked) > 1 or len(gray_marks) > 0
        result.append(q)
    return result


def _draw_annotations(
    warped, markers, copy_positions: dict, page: int, questions: list[dict]
) -> None:
    s = warped.shape[1] / PAGE_W_PT
    M = cv2.getPerspectiveTransform(markers, _dst_points(s))
    pts = cv2.perspectiveTransform(markers.reshape(-1, 1, 2), M).reshape(-1, 2)
    for x, y in pts:
        cv2.circle(warped, (int(x), int(y)), 12, (0, 200, 0), 2)
    cv2.rectangle(
        warped,
        (int(355 * s), int(10 * s)),
        (int(455 * s), int(112 * s)),
        (255, 0, 0),
        2,
    )
    qmap = {q["qid"]: q for q in questions}
    for b in copy_positions["bubbles"]:
        if b["page"] != page:
            continue
        cx = int((b["x_pt"] + BUBBLE_DX_PT) * s)
        cy = int((b["y_pt"] + BUBBLE_DY_PT) * s)
        q = qmap[b["qid"]]
        if b["key"] in q["checked"]:
            color = (0, 180, 0)
        elif q["needs_review"]:
            color = (0, 0, 255)
        else:
            color = (160, 160, 160)
        cv2.circle(warped, (cx, cy), int(BUBBLE_R_PT * s), color, 2)


def process_scan(
    path: Path,
    positions: dict,
    annotated_dir: Path | None = None,
    threshold: float = THRESHOLD,
    gray_threshold: float = GRAY_THRESHOLD,
) -> dict:
    """
    Process one full scan: markers, straightening, QR, bubbles, annotation.

    Args:
        path: Scan image file (PNG/JPG).
        positions: ``positions.json`` content (indexed by copy_id).
        annotated_dir: If set, output directory for the annotated image.
        threshold: Fill threshold for a checked bubble.
        gray_threshold: Fill threshold for detecting a gray trace.

    Returns:
        Dict with ``scan``, ``status`` (``ok`` / ``needs_review`` /
        ``unread``), ``copy_id``, ``page``, ``questions``, ``annotated``
        and ``error`` (set if ``unread``).

    Raises:
        ValueError: Raised internally then converted to status ``unread``
            (unreadable image, missing markers, unreadable QR, unknown copy).
    """
    result = {
        "scan": path.name,
        "status": "unread",
        "copy_id": None,
        "page": None,
        "questions": [],
        "annotated": None,
        "error": None,
    }
    try:
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError("unreadable image")
        markers = detect_markers(image)
        warped = unwarp(image, markers)
        qr = read_qr(warped)
        if qr["rot"]:
            warped = np.rot90(warped, -qr["rot"] // 90).copy()
        result["copy_id"] = qr["copy_id"]
        result["page"] = qr["page"]
        if qr["copy_id"] not in positions:
            raise ValueError(f"copy_id {qr['copy_id']} unknown in positions.json")
        copy_pos = positions[qr["copy_id"]]
        result["questions"] = read_bubbles(
            warped, copy_pos, qr["page"], threshold, gray_threshold
        )
        result["status"] = (
            "ok"
            if all(not q["needs_review"] for q in result["questions"])
            else "needs_review"
        )
        if annotated_dir is not None:
            annotated_dir.mkdir(parents=True, exist_ok=True)
            out = annotated_dir / path.name
            _draw_annotations(
                warped, markers, copy_pos, qr["page"], result["questions"]
            )
            cv2.imwrite(str(out), warped)
            result["annotated"] = str(out)
    except Exception as e:
        result["error"] = str(e)
    return result


def aggregate_copies(results: dict, positions: dict) -> dict:
    """
    Aggregate results per copy (multi-page).

    Args:
        results: ``scans`` section of the OMR results (by scan name).
        positions: ``positions.json`` content.

    Returns:
        Dict indexed by copy_id: ``status`` (``ok`` / ``needs_review`` /
        ``partial`` if pages are missing / ``unread`` if unknown copy),
        ``pages`` and ``questions`` (with their ``page``), sorted.
    """
    by_copy: dict[str, dict] = {}
    for r in results.values():
        if r["status"] == "unread" or r["copy_id"] is None:
            continue
        cid = r["copy_id"]
        c = by_copy.setdefault(cid, {"pages": [], "questions": []})
        if r["page"] not in c["pages"]:
            c["pages"].append(r["page"])
            c["questions"].extend(dict(q, page=r["page"]) for q in r["questions"])
    copies = {}
    for cid, c in by_copy.items():
        if cid not in positions:
            status = "unread"
        else:
            expected = {b["page"] for b in positions[cid]["bubbles"]}
            pages = sorted(set(c["pages"]))
            if pages and set(pages) != expected:
                status = "partial"
            elif any(q["needs_review"] for q in c["questions"]):
                status = "needs_review"
            else:
                status = "ok"
        c["status"] = status
        c["pages"] = sorted(set(c["pages"]))
        c["questions"].sort(key=lambda q: (q["page"], q["qid"]))
        copies[cid] = c
    return copies


def main() -> None:
    """
    CLI entry point ``mini-amc-omr``.

    Reads the scans from ``--scans`` and writes ``--out`` as
    ``{"scans": …, "copies": …}``, plus the annotated images in
    ``--annotated``.
    """
    ap = argparse.ArgumentParser(description="OMR reading of scanned answer sheets")
    ap.add_argument("--scans", type=Path, default=Path("scans"))
    ap.add_argument("--positions", type=Path, default=Path("data/positions.json"))
    ap.add_argument("--out", type=Path, default=Path("data/omr_results.json"))
    ap.add_argument("--annotated", type=Path, default=Path("data/annotated"))
    ap.add_argument("--threshold", type=float, default=THRESHOLD)
    ap.add_argument("--gray-threshold", type=float, default=GRAY_THRESHOLD)
    args = ap.parse_args()

    if not args.scans.is_dir():
        ap.error(f"scans directory not found: {args.scans}")
    if not args.positions.exists():
        ap.error(f"positions file not found: {args.positions} (run mini-amc-gen first)")
    positions = json.loads(args.positions.read_text(encoding="utf-8"))
    scans = (
        sorted(args.scans.glob("*.png"))
        + sorted(args.scans.glob("*.jpg"))
        + sorted(args.scans.glob("*.jpeg"))
    )
    results = {}
    for scan in scans:
        results[scan.name] = process_scan(
            scan, positions, args.annotated, args.threshold, args.gray_threshold
        )
    output = {"scans": results, "copies": aggregate_copies(results, positions)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
