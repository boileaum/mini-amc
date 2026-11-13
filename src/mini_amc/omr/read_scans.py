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
FILL_THRESHOLD = 0.35
QR_RE = re.compile(r"copy:(\d+)\|page:(\d+)")


def detect_markers(image) -> np.ndarray:
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
    if len(cands) != 4:
        raise ValueError(f"{len(cands)} marqueurs trouvés (4 requis)")
    cands.sort(key=lambda p: p[1])
    top = sorted(cands[:2], key=lambda p: p[0])
    bottom = sorted(cands[2:], key=lambda p: p[0])
    return np.array([top[0], top[1], bottom[1], bottom[0]], dtype=np.float32)


def _dst_points(scale: float) -> np.ndarray:
    m = MARKER_CENTER_PT * scale
    w = PAGE_W_PT * scale
    h = PAGE_H_PT * scale
    return np.array([[m, m], [w - m, m], [w - m, h - m], [m, h - m]], dtype=np.float32)


def unwarp(image, markers, scale: float = SCALE):
    M = cv2.getPerspectiveTransform(markers, _dst_points(scale))
    return cv2.warpPerspective(
        image,
        M,
        (round(PAGE_W_PT * scale), round(PAGE_H_PT * scale)),
        borderValue=(255, 255, 255),
    )


def read_qr(warped) -> dict:
    s = warped.shape[1] / PAGE_W_PT
    h = warped.shape[0]
    crops = [
        (350, 470, 0, 130),
        (300, 595, 0, 160),
        (0, 595, 0, 200),
        (0, PAGE_W_PT, 0, PAGE_H_PT),
    ]
    det = cv2.QRCodeDetector()
    for x0, x1, y0, y1 in crops:
        crop = warped[
            max(0, int(y0 * s)) : min(h, int(y1 * s)),
            max(0, int(x0 * s)) : min(warped.shape[1], int(x1 * s)),
        ]
        for img in (
            crop,
            cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC),
        ):
            data, _, _ = det.detectAndDecode(img)
            m = QR_RE.fullmatch(data or "")
            if m:
                return {"copy_id": m.group(1), "page": int(m.group(2))}
    raise ValueError("QR illisible")


def read_bubbles(warped, copy_positions: dict, page: int) -> list[dict]:
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
        if fill > FILL_THRESHOLD:
            q["checked"].append(b["key"])
    result = []
    for qid in sorted(questions):
        q = questions[qid]
        q["a_verifier"] = len(q["checked"]) != 1
        q["fills"] = dict(sorted(q["fills"].items()))
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
        elif q["a_verifier"]:
            color = (0, 0, 255)
        else:
            color = (160, 160, 160)
        cv2.circle(warped, (cx, cy), int(BUBBLE_R_PT * s), color, 2)


def process_scan(
    path: Path, positions: dict, annotated_dir: Path | None = None
) -> dict:
    result = {
        "scan": path.name,
        "status": "non_lu",
        "copy_id": None,
        "page": None,
        "questions": [],
        "annotated": None,
        "error": None,
    }
    try:
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError("image illisible")
        markers = detect_markers(image)
        warped = unwarp(image, markers)
        qr = read_qr(warped)
        result["copy_id"] = qr["copy_id"]
        result["page"] = qr["page"]
        if qr["copy_id"] not in positions:
            raise ValueError(f"copy_id {qr['copy_id']} inconnu de positions.json")
        copy_pos = positions[qr["copy_id"]]
        result["questions"] = read_bubbles(warped, copy_pos, qr["page"])
        result["status"] = (
            "ok"
            if all(not q["a_verifier"] for q in result["questions"])
            else "a_verifier"
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


def main() -> None:
    ap = argparse.ArgumentParser(description="Lecture OMR des scans de copies")
    ap.add_argument("--scans", type=Path, default=Path("scans"))
    ap.add_argument("--positions", type=Path, default=Path("data/positions.json"))
    ap.add_argument("--out", type=Path, default=Path("data/omr_results.json"))
    ap.add_argument("--annotated", type=Path, default=Path("data/annotated"))
    args = ap.parse_args()

    positions = json.loads(args.positions.read_text(encoding="utf-8"))
    scans = (
        sorted(args.scans.glob("*.png"))
        + sorted(args.scans.glob("*.jpg"))
        + sorted(args.scans.glob("*.jpeg"))
    )
    results = {}
    for scan in scans:
        results[scan.name] = process_scan(scan, positions, args.annotated)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
