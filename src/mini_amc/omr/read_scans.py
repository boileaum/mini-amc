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
SEUIL = 0.35
SEUIL_GRIS = 0.15
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


def _qr_rotation(warped, det) -> int:
    ok, points = det.detect(warped)
    if not ok or points is None or len(points) == 0:
        return 0
    c = points[0].mean(axis=0)
    h, w = warped.shape[:2]
    s = w / PAGE_W_PT
    ex, ey = 405 * s, 65 * s
    ang_m = float(np.degrees(np.arctan2(c[1] - h / 2, c[0] - w / 2)))
    ang_e = float(np.degrees(np.arctan2(ey - h / 2, ex - w / 2)))
    return int(round((ang_m - ang_e) / 90) % 4) * 90


def read_qr(warped) -> dict:
    s = warped.shape[1] / PAGE_W_PT
    h, w = warped.shape[:2]
    crops = [
        warped[0 : int(130 * s), int(340 * s) : min(w, int(470 * s))],
        warped[0 : int(160 * s), int(300 * s) : w],
        warped[0 : int(200 * s), 0:w],
        warped,
    ]
    det = cv2.QRCodeDetector()
    rot = _qr_rotation(warped, det)
    for crop in crops:
        for img in (
            crop,
            cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC),
        ):
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            for variant in (img, bw):
                ok, decoded, _, _ = det.detectAndDecodeMulti(variant)
                texts = list(decoded) if ok and decoded else []
                if not texts:
                    data, _, _ = det.detectAndDecode(variant)
                    if data:
                        texts = [data]
                for t in texts:
                    m = QR_RE.fullmatch(t or "")
                    if m:
                        return {
                            "copy_id": m.group(1),
                            "page": int(m.group(2)),
                            "rot": rot,
                        }
    raise ValueError("QR illisible")


def read_bubbles(
    warped,
    copy_positions: dict,
    page: int,
    seuil: float = SEUIL,
    seuil_gris: float = SEUIL_GRIS,
) -> list[dict]:
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
        checked = [k for k, f in q["fills"].items() if f >= seuil]
        gris = [k for k, f in q["fills"].items() if seuil_gris <= f < seuil]
        q["checked"] = checked
        q["a_verifier"] = len(checked) > 1 or len(gris) > 0
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
    path: Path,
    positions: dict,
    annotated_dir: Path | None = None,
    seuil: float = SEUIL,
    seuil_gris: float = SEUIL_GRIS,
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
        if qr["rot"]:
            warped = np.rot90(warped, -qr["rot"] // 90).copy()
        result["copy_id"] = qr["copy_id"]
        result["page"] = qr["page"]
        if qr["copy_id"] not in positions:
            raise ValueError(f"copy_id {qr['copy_id']} inconnu de positions.json")
        copy_pos = positions[qr["copy_id"]]
        result["questions"] = read_bubbles(
            warped, copy_pos, qr["page"], seuil, seuil_gris
        )
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


def aggregate_copies(results: dict, positions: dict) -> dict:
    by_copy: dict[str, dict] = {}
    for r in results.values():
        if r["status"] == "non_lu" or r["copy_id"] is None:
            continue
        cid = r["copy_id"]
        c = by_copy.setdefault(cid, {"pages": [], "questions": []})
        if r["page"] not in c["pages"]:
            c["pages"].append(r["page"])
            c["questions"].extend(dict(q, page=r["page"]) for q in r["questions"])
    copies = {}
    for cid, c in by_copy.items():
        if cid not in positions:
            status = "non_lu"
        else:
            expected = {b["page"] for b in positions[cid]["bubbles"]}
            pages = sorted(set(c["pages"]))
            if pages and set(pages) != expected:
                status = "partiel"
            elif any(q["a_verifier"] for q in c["questions"]):
                status = "a_verifier"
            else:
                status = "ok"
        c["status"] = status
        c["pages"] = sorted(set(c["pages"]))
        c["questions"].sort(key=lambda q: (q["page"], q["qid"]))
        copies[cid] = c
    return copies


def main() -> None:
    ap = argparse.ArgumentParser(description="Lecture OMR des scans de copies")
    ap.add_argument("--scans", type=Path, default=Path("scans"))
    ap.add_argument("--positions", type=Path, default=Path("data/positions.json"))
    ap.add_argument("--out", type=Path, default=Path("data/omr_results.json"))
    ap.add_argument("--annotated", type=Path, default=Path("data/annotated"))
    ap.add_argument("--seuil", type=float, default=SEUIL)
    ap.add_argument("--seuil-gris", type=float, default=SEUIL_GRIS)
    args = ap.parse_args()

    positions = json.loads(args.positions.read_text(encoding="utf-8"))
    scans = (
        sorted(args.scans.glob("*.png"))
        + sorted(args.scans.glob("*.jpg"))
        + sorted(args.scans.glob("*.jpeg"))
    )
    results = {}
    for scan in scans:
        results[scan.name] = process_scan(
            scan, positions, args.annotated, args.seuil, args.seuil_gris
        )
    output = {"scans": results, "copies": aggregate_copies(results, positions)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
