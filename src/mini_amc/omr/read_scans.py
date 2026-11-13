import argparse
import json
from pathlib import Path


def detect_markers(image):
    raise NotImplementedError("D4 : 4 carrés noirs -> coordonnées")


def unwarp(image, markers):
    raise NotImplementedError("D4 : homographie -> page redressée")


def read_qr(warped):
    raise NotImplementedError("D5 : cv2.QRCodeDetector -> copy_id + page")


def read_bubbles(warped, positions):
    raise NotImplementedError("D4-D5 : densité pixels par case + flag a_verifier")


def process_scan(path: Path, positions: dict) -> dict:
    raise NotImplementedError("D4-D6 : pipeline complet + image annotée")


def main() -> None:
    ap = argparse.ArgumentParser(description="Lecture OMR des scans de copies")
    ap.add_argument("--scans", type=Path, default=Path("scans"))
    ap.add_argument("--positions", type=Path, default=Path("data/positions.json"))
    ap.add_argument("--out", type=Path, default=Path("data/omr_results.json"))
    args = ap.parse_args()

    positions = json.loads(args.positions.read_text(encoding="utf-8"))
    scans = (
        sorted(args.scans.glob("*.png"))
        + sorted(args.scans.glob("*.jpg"))
        + sorted(args.scans.glob("*.jpeg"))
    )
    results = {}
    for scan in scans:
        results[scan.name] = process_scan(scan, positions)
    args.out.write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
