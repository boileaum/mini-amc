"""Single CLI entry point ``mini-amc`` with subcommands (argparse, no dependency)."""

import argparse
import os
import sys
from pathlib import Path

import uvicorn

from mini_amc.grade.notes import BAREMES

_COMMANDS = {
    "init": (
        "mini_amc.scaffold",
        "Create an exam project dir with the example files (bank, CSVs, runbook)",
    ),
    "preview": (
        "mini_amc.preview",
        "Render one copy to check the layout (./preview, --png, --watch)",
    ),
    "generate": (
        "mini_amc.gen.generate",
        "Generate the exam copies (Typst PDFs, positions, answers)",
    ),
    "omr": (
        "mini_amc.omr.read_scans",
        "OMR reading of the scans (markers, homography, QR, bubbles, grade boxes)",
    ),
    "grades": (
        "mini_amc.grade.notes",
        "Grades (bareme v1) + CSV export (notes.csv, notes_detail.csv)",
    ),
}


def _web(rest: list[str]) -> None:
    ap = argparse.ArgumentParser(
        prog="mini-amc web", description="Review web UI (FastAPI)"
    )
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--reload", action="store_true")
    ap.add_argument(
        "--data",
        type=Path,
        default=Path("data"),
        help="project data dir (default: ./data; also via MINI_AMC_DATA)",
    )
    ap.add_argument(
        "--bareme",
        choices=sorted(BAREMES),
        default=None,
        help="grading scheme for the live score (default: data/config.json)",
    )
    args = ap.parse_args(rest)
    os.environ["MINI_AMC_DATA"] = str(args.data.resolve())
    if args.bareme:
        os.environ["MINI_AMC_BAREME"] = args.bareme
    uvicorn.run(
        "mini_amc.web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def main(argv: list[str] | None = None) -> None:
    """
    CLI entry point ``mini-amc``.

    Subcommands: ``generate``, ``omr``, ``grades`` (delegated to the
    corresponding module, remaining args passed through) and ``web``
    (review UI via uvicorn).

    Args:
        argv: Command line arguments (defaults to ``sys.argv[1:]``).
    """
    argv = sys.argv[1:] if argv is None else argv
    # the subparsers below are declared without arguments, so argparse would
    # not show the subcommand's own --help: delegate -h/--help directly
    if argv and argv[0] in (*_COMMANDS, "web") and argv[1:2] in (["-h"], ["--help"]):
        import importlib

        if argv[0] == "web":
            _web(argv[1:])
        else:
            importlib.import_module(_COMMANDS[argv[0]][0]).main(argv[1:])
        return
    ap = argparse.ArgumentParser(
        prog="mini-amc",
        description=(
            "mini-clone of Auto-Multiple-Choice: QCM generation (Typst), "
            "local OMR, review UI, grades"
        ),
    )
    sub = ap.add_subparsers(dest="command", required=True)
    for name, (_, help_text) in _COMMANDS.items():
        sub.add_parser(name, help=help_text)
    sub.add_parser("web", help="Review web UI (FastAPI + uvicorn)")
    args, rest = ap.parse_known_args(argv)
    if args.command == "web":
        _web(rest)
        return
    module_name, _ = _COMMANDS[args.command]
    import importlib

    importlib.import_module(module_name).main(rest)


if __name__ == "__main__":
    main()
