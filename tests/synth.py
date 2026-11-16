import cv2
import numpy as np
import qrcode

from mini_amc.omr.read_scans import (
    BUBBLE_DX_PT,
    BUBBLE_DY_PT,
    BUBBLE_R_PT,
    PAGE_H_PT,
    PAGE_W_PT,
    SCALE,
    SQUARE_DX_PT,
    SQUARE_DY_PT,
    SQUARE_SIZE_PT,
)


def bubble_center(b):
    if b.get("shape") == "square":
        dx, dy = SQUARE_DX_PT, SQUARE_DY_PT
    else:
        dx, dy = BUBBLE_DX_PT, BUBBLE_DY_PT
    return int((b["x_pt"] + dx) * SCALE), int((b["y_pt"] + dy) * SCALE)


W = round(PAGE_W_PT * SCALE)
H = round(PAGE_H_PT * SCALE)
MARKER_PX = round(1.2 * 72 / 2.54 * SCALE)
CORNER_PX = round(0.7 * 72 / 2.54 * SCALE)
QR_PX = round(3.0 * 72 / 2.54 * SCALE)
QR_X0 = W - round(2.2 * 72 / 2.54 * SCALE) - QR_PX
QR_Y0 = CORNER_PX


def _bubble_pos(qid, key, idx, page=1, shape="circle", multi=False):
    return {
        "qid": qid,
        "key": key,
        "page": page,
        "x_pt": 100.0,
        "y_pt": 200.0 + 22.0 * idx,
        "shape": shape,
        "multi": multi,
    }


def _draw_bubble(img, b, filled=False):
    cx, cy = bubble_center(b)
    if b.get("shape") == "square":
        half = int(SQUARE_SIZE_PT * SCALE / 2)
        if filled:
            cv2.rectangle(
                img, (cx - half, cy - half), (cx + half, cy + half), (0, 0, 0), -1
            )
        cv2.rectangle(
            img,
            (cx - half, cy - half),
            (cx + half, cy + half),
            (0, 0, 0),
            max(1, int(SCALE)),
        )
    else:
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
    img[QR_Y0 : QR_Y0 + QR_PX, QR_X0 : QR_X0 + QR_PX] = cv2.cvtColor(
        qr_img, cv2.COLOR_GRAY2BGR
    )
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


def _warp_photo(img, out_path, seed=1, margin=120, jitter=40):
    h, w = img.shape[:2]
    rng = np.random.default_rng(seed)
    src = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    dst = src + rng.uniform(-jitter, jitter, src.shape).astype(np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    photo = cv2.warpPerspective(
        img, M, (w + margin, h + margin), borderValue=(200, 200, 200)
    )
    cv2.imwrite(str(out_path), photo)
    return out_path
