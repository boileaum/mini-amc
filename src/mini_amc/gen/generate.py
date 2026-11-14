"""QCM exam copy generation: seeded shuffle, Typst compilation, bubble positions."""

import argparse
import csv
import io
import json
import random
import re
import shutil
import string
import subprocess
from pathlib import Path

import qrcode
import yaml

MAX_PAGES = 64
COPY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
PAGE_W_CM = 21.0
PAGE_H_CM = 29.7
CM_TO_PT = 72 / 2.54


def load_bank(path: Path) -> dict:
    """
    Load and validate a YAML question bank.

    Args:
        path: Bank file path (e.g. ``bank.example.yml``).

    Returns:
        The parsed bank (dict with ``meta`` and ``questions``).

    Raises:
        ValueError: Empty bank, duplicate/missing ids, an MCQ question
            without exactly one ``correct`` choice or with a choice count
            outside [2, 26], or an open question with invalid
            ``max_points`` / with ``choices``.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    questions = data.get("questions", [])
    if not questions:
        raise ValueError("empty bank: no questions")
    ids = [q.get("id") for q in questions]
    if any(i is None for i in ids):
        raise ValueError("every question needs an id")
    if len(set(ids)) != len(ids):
        raise ValueError(
            f"duplicate question ids: {sorted({i for i in ids if ids.count(i) > 1})}"
        )
    for q in questions:
        if "text" not in q:
            raise ValueError(f"question {q.get('id')}: 'text' required")
        if q.get("type", "mcq") == "open":
            if "choices" in q:
                raise ValueError(
                    f"question {q.get('id')}: open question must not have choices"
                )
            mp = q.get("max_points")
            if not isinstance(mp, int) or isinstance(mp, bool) or mp < 1:
                raise ValueError(
                    f"question {q.get('id')}: open question needs max_points (int >= 1)"
                )
            if mp > 20:
                raise ValueError(f"question {q.get('id')}: max_points <= 20")
            continue
        if "choices" not in q:
            raise ValueError(f"question {q.get('id')}: 'choices' required")
        correct = [c for c in q["choices"] if c.get("correct")]
        if len(correct) != 1:
            raise ValueError(
                f"question {q.get('id')}: exactly 1 correct choice required in v1"
            )
        if len(q["choices"]) < 2:
            raise ValueError(f"question {q.get('id')}: at least 2 choices required")
        if len(q["choices"]) > len(string.ascii_uppercase):
            raise ValueError(f"question {q.get('id')}: at most 26 choices (keys A-Z)")
    return data


def load_students(
    path: Path,
    id_column: str = "copy_id",
    name_columns: list[str] | None = None,
    delimiter: str = "",
) -> dict[str, str]:
    """
    Load a nominative CSV and map copy ids to student names.

    Flexible on the format (e.g. Moodle exports): the delimiter is
    auto-detected when not given, the link column and the name column(s)
    are designated by the caller, and all other columns are ignored.

    Args:
        path: CSV file path (UTF-8, BOM accepted).
        id_column: Column whose values become the copy ids (the link
            between a student and a copy). Values must be unique,
            non-empty and match ``[A-Za-z0-9][A-Za-z0-9_.-]*`` (they are
            used in file names and QR contents).
        name_columns: Column(s) joined with a space to form the display
            name (default ``["name"]``).
        delimiter: CSV delimiter; empty string = auto-detect among
            ``, ; tab |``.

    Returns:
        Dict ``copy_id`` -> student name, in CSV order.

    Raises:
        ValueError: Missing column, empty/duplicate/invalid copy id,
            empty name, or no student rows.
    """
    if name_columns is None:
        name_columns = ["name"]
    text = path.read_text(encoding="utf-8-sig")
    if not delimiter:
        try:
            delimiter = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|").delimiter
        except csv.Error:
            delimiter = ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    fieldnames = reader.fieldnames or []
    absent = [c for c in [id_column, *name_columns] if c not in fieldnames]
    if absent:
        raise ValueError(f"{path}: missing column(s) {absent} (header: {fieldnames})")
    students = {}
    for lineno, row in enumerate(reader, start=2):
        cid = (row.get(id_column) or "").strip()
        if not cid:
            raise ValueError(f"{path}: line {lineno}: empty {id_column!r}")
        if not COPY_ID_RE.match(cid):
            raise ValueError(
                f"{path}: line {lineno}: invalid copy id {cid!r} "
                "(allowed: letters, digits, _ . -)"
            )
        if cid in students:
            raise ValueError(f"{path}: duplicate copy id {cid!r}")
        name = " ".join(" ".join((row.get(c) or "").split()) for c in name_columns)
        if not name:
            raise ValueError(
                f"{path}: line {lineno}: empty name from column(s) {name_columns}"
            )
        students[cid] = name
    if not students:
        raise ValueError(f"{path}: no student rows")
    return students


def plan_copies(bank: dict, copy_ids: list[str], seed: int) -> list[dict]:
    """
    Plan the copies: seeded shuffle of questions and choices.

    The bank is not mutated. Each copy gets keys A, B, C… reassigned
    according to the shuffled order, and an ``answers`` dict
    (``qid`` -> correct key).

    Args:
        bank: Bank validated by :func:`load_bank`.
        copy_ids: Copy identifiers (``0001``, ``0002``… by default, or the
            values of the students CSV link column). Must be unique and
            non-empty.
        seed: Random generator seed (reproducibility).

    Returns:
        List of copies, each with ``copy_id``, ``meta``, ``questions``
        and ``answers``.

    Raises:
        ValueError: Empty or duplicate ``copy_ids``.
    """
    if not copy_ids:
        raise ValueError("no copy ids")
    if len(set(copy_ids)) != len(copy_ids):
        raise ValueError("duplicate copy ids")
    rng = random.Random(seed)
    questions = bank["questions"]
    copies = []
    for copy_id in copy_ids:
        answers = {}
        copy_questions = []
        for q in rng.sample(questions, len(questions)):
            if q.get("type", "mcq") == "open":
                copy_questions.append(
                    {
                        "id": q["id"],
                        "text": q["text"],
                        "type": "open",
                        "max_points": q["max_points"],
                    }
                )
                answers[q["id"]] = "open"
                continue
            choices = rng.sample(q["choices"], len(q["choices"]))
            copy_choices = []
            for c, key in zip(choices, string.ascii_uppercase, strict=False):
                copy_choices.append(
                    {"key": key, "text": c["text"], "correct": bool(c.get("correct"))}
                )
                if c.get("correct"):
                    answers[q["id"]] = key
            copy_questions.append(
                {
                    "id": q["id"],
                    "text": q["text"],
                    "type": "mcq",
                    "choices": copy_choices,
                }
            )
        copies.append(
            {
                "copy_id": copy_id,
                "meta": bank.get("meta", {}),
                "questions": copy_questions,
                "answers": answers,
            }
        )
    return copies


def _require_typst() -> str:
    typst = shutil.which("typst")
    if typst is None:
        raise RuntimeError(
            "`typst` binary not found in PATH (v0.15.1 required, see README)"
        )
    return typst


def compile_copy(template_dir: Path, copy: dict, out_pdf: Path) -> Path:
    """
    Compile one copy to PDF via ``typst compile``.

    Prepares an isolated build directory (``<out>/build/<copy_id>/``:
    ``main.typ`` + ``copy.json`` + ``qr-1..MAX_PAGES.png``) because Typst
    resolves relative paths against the compiled file.

    Args:
        template_dir: Directory containing ``main.typ``.
        copy: Copy (dict without ``answers``) written as ``copy.json``.
        out_pdf: Output PDF path.

    Returns:
        The build directory used.

    Raises:
        RuntimeError: ``typst`` missing from PATH, compilation failure,
            or copy exceeding ``MAX_PAGES`` pages.
    """
    typst = _require_typst()
    copy_id = copy["copy_id"]
    build = out_pdf.parent / "build" / copy_id
    build.mkdir(parents=True, exist_ok=True)
    shutil.copy(template_dir / "main.typ", build / "main.typ")
    (build / "copy.json").write_text(
        json.dumps(copy, ensure_ascii=False), encoding="utf-8"
    )
    for n in range(1, MAX_PAGES + 1):
        qrcode.make(f"copy:{copy_id}|page:{n}").save(build / f"qr-{n}.png")
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [typst, "compile", "main.typ", str(out_pdf.resolve())],
        cwd=build,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        if "qr-" in proc.stderr and "not found" in proc.stderr:
            raise RuntimeError(
                f"copy {copy_id}: more than {MAX_PAGES} pages "
                f"(missing QR qr-{MAX_PAGES + 1}.png)"
            )
        raise RuntimeError(f"typst compile failed for copy {copy_id}:\n{proc.stderr}")
    return build


def export_positions(build_dir: Path, copy_id: str) -> dict:
    """
    Extract the bubble positions of a copy via ``typst eval``.

    Queries the template's ``#metadata(...)`` and converts coordinates
    to points (float, ``pt`` suffix stripped).

    Args:
        build_dir: Build directory produced by :func:`compile_copy`.
        copy_id: Copy identifier (key in ``positions.json``).

    Returns:
        Dict with ``copy_id``, ``page`` (``w_pt``/``h_pt``), ``questions``,
        ``bubbles`` (each with ``qid``, ``page``, ``x_pt``, ``y_pt``,
        plus ``key`` for bubbles) and ``gradeboxes`` (same, plus ``value``
        for open questions).

    Raises:
        RuntimeError: ``typst`` missing or ``typst eval`` failure.
    """
    _require_typst()
    proc = subprocess.run(
        ["typst", "eval", "query(metadata).map(it => it.value)", "--in", "main.typ"],
        cwd=build_dir,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"typst eval failed for copy {copy_id}:\n{proc.stderr}")
    metas = json.loads(proc.stdout)

    def _pos(m: dict) -> dict:
        return {
            "qid": m["qid"],
            "page": m["page"],
            "x_pt": float(str(m["x"]).removesuffix("pt")),
            "y_pt": float(str(m["y"]).removesuffix("pt")),
        }

    return {
        "copy_id": copy_id,
        "page": {
            "w_pt": round(PAGE_W_CM * CM_TO_PT, 2),
            "h_pt": round(PAGE_H_CM * CM_TO_PT, 2),
        },
        "questions": [_pos(m) for m in metas if m["kind"] == "question"],
        "bubbles": [
            {**_pos(m), "key": m["key"]} for m in metas if m["kind"] == "bubble"
        ],
        "gradeboxes": [
            {**_pos(m), "value": m["value"]} for m in metas if m["kind"] == "gradebox"
        ],
    }


def main() -> None:
    """
    CLI entry point ``mini-amc-gen``.

    Produces in ``--out``: ``copy_XXXX.json``, ``copy_XXXX.pdf``,
    ``positions.json`` (indexed by copy_id) and ``answers.json``.
    With ``--students CSV``, the CSV link column provides the copy ids
    (default column ``copy_id``, e.g. ``Numéro étudiant`` in a Moodle
    export) and the name column(s) the student names; also writes
    ``students.json`` and adds a ``student`` field to each copy JSON.
    Everything is staged in ``--out/.staging`` and moved into place
    only when the whole generation succeeds: a failure leaves ``--out``
    untouched.
    """
    ap = argparse.ArgumentParser(description="Generate QCM exam copies (Typst)")
    ap.add_argument("--bank", type=Path, default=Path("bank.example.yml"))
    ap.add_argument("--copies", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--template", type=Path, default=Path("template"))
    ap.add_argument("--students", type=Path, default=None)
    ap.add_argument("--students-id-column", default="copy_id")
    ap.add_argument("--students-name-columns", default="name")
    ap.add_argument("--students-delimiter", default="")
    ap.add_argument("--out", type=Path, default=Path("data"))
    args = ap.parse_args()

    if args.copies < 1:
        ap.error("--copies must be >= 1")
    bank = load_bank(args.bank)
    students = None
    if args.students is not None:
        name_columns = [
            c.strip() for c in args.students_name_columns.split(",") if c.strip()
        ]
        students = load_students(
            args.students,
            id_column=args.students_id_column,
            name_columns=name_columns,
            delimiter=args.students_delimiter,
        )
        if len(students) != args.copies:
            ap.error(
                f"--students {args.students} has {len(students)} rows "
                f"but --copies is {args.copies}"
            )
        copy_ids = list(students)
    else:
        copy_ids = [f"{i:04d}" for i in range(1, args.copies + 1)]
    args.out.mkdir(parents=True, exist_ok=True)

    stage = args.out / ".staging"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    try:
        copies = plan_copies(bank, copy_ids, args.seed)
        if students is not None:
            for copy in copies:
                copy["student"] = students[copy["copy_id"]]
            (stage / "students.json").write_text(
                json.dumps(students, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        positions = {}
        for copy in copies:
            copy_id = copy["copy_id"]
            copy_json = {k: v for k, v in copy.items() if k != "answers"}
            (stage / f"copy_{copy_id}.json").write_text(
                json.dumps(copy_json, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            build = compile_copy(
                args.template, copy_json, stage / f"copy_{copy_id}.pdf"
            )
            positions[copy_id] = export_positions(build, copy_id)
        (stage / "positions.json").write_text(
            json.dumps(positions, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        answers = {c["copy_id"]: c["answers"] for c in copies}
        (stage / "answers.json").write_text(
            json.dumps(answers, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        if (args.out / "build").exists():
            shutil.rmtree(args.out / "build")
        for item in sorted(stage.iterdir()):
            shutil.move(str(item), args.out / item.name)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    shutil.rmtree(stage, ignore_errors=True)


if __name__ == "__main__":
    main()
