"""``mini-amc preview``: render a single copy to check the layout."""

import argparse
import json
import subprocess
import threading
import time
from pathlib import Path

from mini_amc.gen.generate import (
    compile_copy,
    default_template,
    load_bank,
    plan_copies,
)

PREVIEW_COPY_ID = "0001"


def write_copy_json(build_dir: Path, bank_path: Path, seed: int) -> Path:
    """
    (Re)write ``copy.json`` of the preview copy into an existing build dir.

    Args:
        build_dir: Build directory produced by :func:`compile_copy`.
        bank_path: Question bank YAML.
        seed: Shuffle seed.

    Returns:
        The ``copy.json`` path written.
    """
    bank = load_bank(bank_path)
    (copy,) = plan_copies(bank, [PREVIEW_COPY_ID], seed)
    copy_json = {k: v for k, v in copy.items() if k != "answers"}
    path = build_dir / "copy.json"
    path.write_text(json.dumps(copy_json, ensure_ascii=False), encoding="utf-8")
    return path


def build_preview(bank_path: Path, out_dir: Path, seed: int, template: Path) -> Path:
    """
    Generate and compile one preview copy.

    Args:
        bank_path: Question bank YAML.
        out_dir: Preview output directory (``./preview`` by default).
        seed: Shuffle seed (fixed by default for a stable preview).
        template: Template directory.

    Returns:
        The PDF path.
    """
    bank = load_bank(bank_path)
    (copy,) = plan_copies(bank, [PREVIEW_COPY_ID], seed)
    copy_json = {k: v for k, v in copy.items() if k != "answers"}
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = out_dir / f"copy_{PREVIEW_COPY_ID}.pdf"
    compile_copy(template, copy_json, pdf)
    return pdf


def render_pngs(build_dir: Path, out_dir: Path, ppi: int = 120) -> list[Path]:
    """
    Render the preview PDF pages to PNG (via ``typst compile`` in the build dir).

    Args:
        build_dir: Build directory (self-contained: main.typ, copy.json, qr PNGs).
        out_dir: Where to write ``page-N.png``.
        ppi: Render resolution.

    Returns:
        The PNG paths written.

    Raises:
        RuntimeError: ``typst compile`` failure.
    """
    proc = subprocess.run(
        [
            "typst",
            "compile",
            "main.typ",
            str(out_dir / "page-{p}.png"),
            "--ppi",
            str(ppi),
        ],
        cwd=build_dir,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"typst compile (png) failed:\n{proc.stderr}")
    return sorted(out_dir.glob("page-*.png"))


def main(argv: list[str] | None = None) -> None:
    """
    Subcommand ``mini-amc preview`` (via ``mini_amc.cli``).

    Renders ONE copy (id ``0001``, fixed seed) into ``--out`` (default
    ``./preview``, gitignored) without touching ``./data``. ``--png`` also
    renders the pages to PNG; ``--watch`` keeps re-rendering with
    ``typst watch`` and regenerates ``copy.json`` whenever the bank changes.
    Plain ``typst compile main.typ out.pdf`` / ``typst watch`` also work in
    the self-contained build dir `<out>/build/0001/`.

    Args:
        argv: Command line arguments (defaults to ``sys.argv[1:]``).
    """
    ap = argparse.ArgumentParser(
        prog="mini-amc preview",
        description="Render a single copy to check the layout (no ./data touched)",
    )
    ap.add_argument("--bank", type=Path, default=Path("bank.example.yml"))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=Path("preview"))
    ap.add_argument("--template", type=Path, default=None)
    ap.add_argument("--png", action="store_true", help="also render pages to PNG")
    ap.add_argument(
        "--watch", action="store_true", help="re-render on change (typst watch)"
    )
    args = ap.parse_args(argv)
    if args.template is None:
        args.template = default_template()

    pdf = build_preview(args.bank, args.out, args.seed, args.template)
    build_dir = args.out / "build" / PREVIEW_COPY_ID
    print(f"preview PDF: {pdf}")
    if args.png:
        # absolute path: typst runs with cwd=build_dir
        pngs = render_pngs(build_dir, args.out.resolve())
        print(f"preview PNGs: {', '.join(p.name for p in pngs)}")
    if not args.watch:
        return

    # watch mode: typst watch recompiles when copy.json/main.typ change; a
    # thread regenerates copy.json when the bank file changes
    procs = [
        subprocess.Popen(
            ["typst", "watch", "main.typ", str(pdf.resolve())],
            cwd=build_dir,
        )
    ]
    if args.png:
        procs.append(
            subprocess.Popen(
                [
                    "typst",
                    "watch",
                    "main.typ",
                    str((args.out / "page-{p}.png").resolve()),
                    "--ppi",
                    "120",
                ],
                cwd=build_dir,
            )
        )

    stop = threading.Event()

    def watch_bank() -> None:
        mtime = args.bank.stat().st_mtime
        while not stop.wait(1.0):
            if args.bank.stat().st_mtime != mtime:
                mtime = args.bank.stat().st_mtime
                write_copy_json(build_dir, args.bank, args.seed)
                print(f"bank changed: copy.json regenerated ({args.bank})")

    t = threading.Thread(target=watch_bank, daemon=True)
    t.start()
    print("watching (Ctrl-C to stop)…")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        stop.set()
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    main()
