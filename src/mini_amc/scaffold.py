"""``mini-amc init``: scaffold an exam project directory with the example files."""

import argparse
import shutil
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"

EXAMPLE_FILES = [
    "bank.example.yml",
    "students.example.csv",
    "students.moodle.example.csv",
    "runbook.md",
]

# template name -> target dotfile name in the exam project
DOT_FILES = {
    "gitignore.example": ".gitignore",
}


def init_project(directory: Path, force: bool = False) -> list[Path]:
    """
    Copy the example files (bank, students CSVs, runbook) into a project dir.

    Also writes a ``.gitignore`` (from ``gitignore.example``) so local data
    (``data/``, ``scans/``, ``preview/``) is never committed when the exam
    folder is tracked with git.

    Args:
        directory: Target directory (created if missing).
        force: Overwrite files that already exist.

    Returns:
        The list of files written.

    Raises:
        FileExistsError: A target file exists and ``force`` is False.
    """
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    targets = [(name, directory / name) for name in EXAMPLE_FILES]
    targets += [(src, directory / dst) for src, dst in DOT_FILES.items()]
    for src_name, dst in targets:
        src = EXAMPLES_DIR / src_name
        if dst.exists() and not force:
            raise FileExistsError(f"{dst} already exists (use --force to overwrite)")
        shutil.copy(src, dst)
        written.append(dst)
    return written


def main(argv: list[str] | None = None) -> None:
    """
    Subcommand ``mini-amc init`` (via ``mini_amc.cli``).

    Creates an exam project directory with the example files:
    ``bank.example.yml``, ``students.example.csv``,
    ``students.moodle.example.csv``, ``runbook.md`` and a ``.gitignore``
    (local data never committed).

    Args:
        argv: Command line arguments (defaults to ``sys.argv[1:]``).
    """
    ap = argparse.ArgumentParser(
        prog="mini-amc init",
        description="Create an exam project dir with the example files",
    )
    ap.add_argument("directory", type=Path, nargs="?", default=Path("."))
    ap.add_argument("--force", action="store_true", help="overwrite existing files")
    args = ap.parse_args(argv)
    written = init_project(args.directory, force=args.force)
    for path in written:
        print(f"created {path}")


if __name__ == "__main__":
    main()
