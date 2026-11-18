"""QCM exam copy generation: seeded shuffle, Typst compilation, bubble positions."""

import argparse
import csv
import io
import json
import os
import random
import re
import shutil
import string
import subprocess
from pathlib import Path
from typing import Any

import qrcode

from mini_amc.grade.notes import DEFAULT_BAREME

MAX_PAGES = 64
# template shipped in the package (used when no ./template dir in the CWD)
PACKAGED_TEMPLATE = Path(__file__).resolve().parents[1] / "template"


def default_template() -> Path:
    """Local ``./template`` if present, else the packaged template."""
    local = Path("template")
    return local if local.is_dir() else PACKAGED_TEMPLATE


# copy ids end up in file names and QR contents: keep them path/QR safe
COPY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
PAGE_W_CM = 21.0
PAGE_H_CM = 29.7
CM_TO_PT = 72 / 2.54


def flatten_content(value: Any) -> str:
    """
    Flatten a Typst value to plain text.

    A statement written in a subject is Typst content: ``typst eval``
    serialises it as nested ``{"func": …}`` nodes, which the review UI and the
    validation cannot use. The PDF keeps the original content; this is only
    the readable projection stored in ``copy_XXXX.json``. Plain strings
    (``choice("Paris")``) are returned as is.

    Args:
        value: String, content node, or list of nodes.

    Returns:
        The text, one line per content line (indentation of code blocks kept),
        with runs of blank lines collapsed.
    """
    # indentation is meaningful in a code block, so only trailing spaces are
    # dropped; a single blank line keeps the paragraphs readable
    lines: list[str] = []
    for line in _flatten(value).splitlines():
        line = line.rstrip()
        if line or (lines and lines[-1]):
            lines.append(line)
    return "\n".join(lines).strip()


def _flatten(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_flatten(item) for item in value)
    if not isinstance(value, dict):
        return ""
    func = value.get("func")
    if func == "space":
        return " "
    if func == "linebreak":
        return "\n"
    if func == "parbreak":
        return "\n\n"
    if func == "equation":
        body = _flatten(value.get("body"))
        return f"$ {body} $" if value.get("block") else f"${body}$"
    if "text" in value:
        return str(value["text"])
    if "body" in value:
        return _flatten(value["body"])
    return _flatten(value.get("children", []))


def load_bank(path: Path) -> dict:
    """
    Read a Typst subject (``amc.typ`` prelude) back into a validated bank.

    Runs ``typst eval`` on an expression that imports the subject and returns
    its ``bank`` value, so the bank is read from the same value the template
    renders: no second parsing of the document, no ``eval`` of the statements.
    The statements are then flattened to plain text (see
    :func:`flatten_content`) for the review UI and the checks.

    Args:
        path: Subject file (e.g. ``subject.typ``).

    Returns:
        The bank (dict with ``meta`` and ``questions``).

    Raises:
        RuntimeError: ``typst`` missing from PATH, or the subject fails to
            evaluate (a bad ``#question`` call, a missing ``amc.typ``, no
            ``bank`` value, …).
        ValueError: The subject defines no question, or the bank breaks a
            rule checked by :func:`validate_bank`.
    """
    typst = _require_typst()
    subject = path.resolve()
    # the eval expression imports the subject by name (cwd is the subject's
    # directory, so its relative imports resolve as usual); json.dumps gives a
    # Typst-compatible string literal, quotes and backslashes included
    code = f"{{ import {json.dumps(subject.name)}: bank; bank }}"
    proc = subprocess.run(
        [typst, "eval", code, "--in", subject.name, "--format", "json"],
        cwd=subject.parent,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"typst eval failed for subject {subject.name}:\n{proc.stderr}"
        )
    data = json.loads(proc.stdout)
    if not isinstance(data, dict):
        raise ValueError(f"{subject.name}: 'bank' must be an #exam(...) value")
    meta = {key: str(data.get(key, "")) for key in ("title", "course", "date")}
    questions = []
    for entry in data.get("questions", []):
        qid = entry.get("id")
        question: dict = {
            "id": None if qid is None else str(qid),
            "text": flatten_content(entry.get("text", "")),
            "type": entry.get("type", "mcq"),
        }
        if question["type"] == "open":
            question["max_points"] = entry.get("max-points")
        else:
            question["choices"] = [
                {
                    "text": flatten_content(choice.get("text", "")),
                    "correct": bool(choice.get("correct", False)),
                }
                for choice in entry.get("choices", [])
            ]
        questions.append(question)
    if not questions:
        raise ValueError(f"{subject.name}: no #question found")
    data = {"meta": meta, "questions": questions}
    validate_bank(data)
    return data


def validate_bank(data: dict) -> None:
    """
    Check a bank against the rules the template and the OMR rely on.

    Args:
        data: Bank dict (``meta`` + ``questions``) read from a subject.

    Raises:
        ValueError: Empty bank, duplicate/missing ids, an MCQ question
            without exactly one ``correct`` choice or with a choice count
            outside [2, 26], or an open question with invalid
            ``max_points`` / with ``choices``.
    """
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
            # grade boxes 0..max_points are drawn in a single row on the copy;
            # 20 keeps that row within the page width
            if mp > 20:
                raise ValueError(f"question {q.get('id')}: max_points <= 20")
            continue
        if "choices" not in q:
            raise ValueError(f"question {q.get('id')}: 'choices' required")
        correct = [c for c in q["choices"] if c.get("correct")]
        # 1..n correct choices: 1 = single-answer MCQ, >1 = multi-answer
        # (rendered with square bubbles)
        if not correct:
            raise ValueError(
                f"question {q.get('id')}: at least 1 correct choice required"
            )
        if len(q["choices"]) < 2:
            raise ValueError(f"question {q.get('id')}: at least 2 choices required")
        if len(q["choices"]) > len(string.ascii_uppercase):
            raise ValueError(f"question {q.get('id')}: at most 26 choices (keys A-Z)")


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
    # utf-8-sig: Moodle/Windows exports often carry a BOM
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
    according to the shuffled order, an ``answers`` dict (``qid`` -> correct
    key) and, per question and choice, the ``src`` index it comes from in the
    bank. The template renders the copy from those indices, so the statements
    reach the PDF as the author's content instead of a flattened copy.

    Args:
        bank: Bank validated by :func:`load_bank`.
        copy_ids: Copy identifiers (``0001``, ``0002``… by default, or the
            values of the students CSV link column). Must be unique and
            non-empty.
        seed: Random generator seed (reproducibility).

    Returns:
        List of copies, each with ``copy_id``, ``meta``, ``questions``
        (``id``, ``src``, ``text``, ``type``, ``choices`` with ``key``,
        ``src``, ``text``, ``correct``) and ``answers``.

    Raises:
        ValueError: Empty or duplicate ``copy_ids``.
    """
    if not copy_ids:
        raise ValueError("no copy ids")
    if len(set(copy_ids)) != len(copy_ids):
        raise ValueError("duplicate copy ids")
    # one shared rng: each copy gets a different shuffle, but the whole run
    # is reproducible from the seed alone
    rng = random.Random(seed)
    questions = bank["questions"]
    copies = []
    for copy_id in copy_ids:
        answers = {}
        copy_questions = []
        for src in rng.sample(range(len(questions)), len(questions)):
            q = questions[src]
            if q.get("type", "mcq") == "open":
                copy_questions.append(
                    {
                        "id": q["id"],
                        "src": src,
                        "text": q["text"],
                        "type": "open",
                        "max_points": q["max_points"],
                    }
                )
                answers[q["id"]] = "open"
                continue
            copy_choices = []
            correct_keys = []
            # keys reassigned A, B, C… in shuffled order; load_bank caps
            # choices at 26, so the zip never truncates
            order = rng.sample(range(len(q["choices"])), len(q["choices"]))
            for src_choice, key in zip(order, string.ascii_uppercase, strict=False):
                choice = q["choices"][src_choice]
                copy_choices.append(
                    {
                        "key": key,
                        "src": src_choice,
                        "text": choice["text"],
                        "correct": bool(choice.get("correct")),
                    }
                )
                if choice.get("correct"):
                    correct_keys.append(key)
            # answers: sorted list of correct keys (a single key for
            # single-answer MCQ, several for multi-answer)
            answers[q["id"]] = sorted(correct_keys)
            copy_questions.append(
                {
                    "id": q["id"],
                    "src": src,
                    "text": q["text"],
                    "type": "mcq",
                    "multi": len(correct_keys) > 1,
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


def compile_root(bank_path: Path, build_dir: Path) -> str:
    """
    Directory to pass as ``--root``: the closest one containing both.

    Typst refuses to read a file outside the root, and the template imports
    the bank from the build dir: the root must cover both. It falls back to
    ``/`` when the bank lives outside the output tree, which keeps working
    without widening anything else.

    Args:
        bank_path: Question bank path.
        build_dir: Build directory of the copy.

    Returns:
        The root directory, as a string.
    """
    paths = [bank_path.resolve().parent, build_dir.resolve()]
    return str(Path(os.path.commonpath([str(p) for p in paths])))


def write_bank_module(bank_path: Path, build: Path) -> None:
    """
    Write the ``bank.typ`` module the template imports.

    One ``#import`` line: the template renders the subject's own value, so the
    statements reach the PDF as the author's content.

    Args:
        bank_path: Subject path.
        build: Build directory.
    """
    # relative import: the build dir sits under the output dir, not next to the
    # subject; --root (see compile_root) makes the .. path legal
    relative = Path(os.path.relpath(bank_path.resolve(), build.resolve()))
    (build / "bank.typ").write_text(
        f"#import {json.dumps(relative.as_posix())}: bank\n", encoding="utf-8"
    )


def compile_copy(
    template_dir: Path, bank_path: Path, copy: dict, out_pdf: Path
) -> Path:
    """
    Compile one copy to PDF via ``typst compile``.

    Prepares an isolated build directory (``<out>/build/<copy_id>/``:
    ``main.typ`` + ``bank.typ`` + ``copy.json`` + ``qr-1..MAX_PAGES.png``)
    because Typst resolves relative paths against the compiled file.

    Args:
        template_dir: Directory containing ``main.typ``.
        bank_path: Subject the copy is rendered from.
        copy: Copy plan (dict without ``answers``) written as ``copy.json``.
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
    write_bank_module(bank_path, build)
    (build / "copy.json").write_text(
        json.dumps(copy, ensure_ascii=False), encoding="utf-8"
    )
    for n in range(1, MAX_PAGES + 1):
        qrcode.make(f"copy:{copy_id}|page:{n}").save(build / f"qr-{n}.png")
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            typst,
            "compile",
            "main.typ",
            str(out_pdf.resolve()),
            "--root",
            compile_root(bank_path, build),
        ],
        cwd=build,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        # only MAX_PAGES QR PNGs are pre-generated; typst fails on the missing
        # qr-N.png when the copy exceeds MAX_PAGES pages
        if "qr-" in proc.stderr and "not found" in proc.stderr:
            raise RuntimeError(
                f"copy {copy_id}: more than {MAX_PAGES} pages "
                f"(missing QR qr-{MAX_PAGES + 1}.png)"
            )
        raise RuntimeError(f"typst compile failed for copy {copy_id}:\n{proc.stderr}")
    return build


def export_positions(build_dir: Path, copy_id: str, root: str) -> dict:
    """
    Extract the bubble positions of a copy via ``typst eval``.

    Queries the template's ``#metadata(...)`` and converts coordinates
    to points (float, ``pt`` suffix stripped).

    Args:
        build_dir: Build directory produced by :func:`compile_copy`.
        copy_id: Copy identifier (key in ``positions.json``).
        root: Typst root directory (see :func:`compile_root`): the template
            imports the bank from outside the build dir.

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
        [
            "typst",
            "eval",
            "query(metadata).map(it => it.value)",
            "--in",
            "main.typ",
            "--root",
            root,
        ],
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
            {
                **_pos(m),
                "key": m["key"],
                "shape": m.get("shape", "circle"),
                "multi": m.get("multi", False),
            }
            for m in metas
            if m["kind"] == "bubble"
        ],
        "gradeboxes": [
            {**_pos(m), "value": m["value"]} for m in metas if m["kind"] == "gradebox"
        ],
    }


def main(argv: list[str] | None = None) -> None:
    """
    Subcommand ``mini-amc generate`` (via ``mini_amc.cli``).

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
    ap = argparse.ArgumentParser(
        prog="mini-amc generate", description="Generate QCM exam copies (Typst)"
    )
    ap.add_argument(
        "--bank",
        type=Path,
        default=Path("subject.typ"),
        help="subject written with the amc.typ prelude",
    )
    ap.add_argument("--copies", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--template",
        type=Path,
        default=None,
        help="template dir (default: ./template if present, else the packaged one)",
    )
    ap.add_argument("--students", type=Path, default=None)
    ap.add_argument("--students-id-column", default="copy_id")
    ap.add_argument("--students-name-columns", default="name")
    ap.add_argument("--students-delimiter", default="")
    ap.add_argument("--out", type=Path, default=Path("data"))
    args = ap.parse_args(argv)

    if args.copies < 1:
        ap.error("--copies must be >= 1")
    if args.template is None:
        args.template = default_template()
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

    # stage everything, move into place only on full success: a failed run
    # must not leave a half-written data/ (old PDFs stay valid until then)
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
                args.template, args.bank, copy_json, stage / f"copy_{copy_id}.pdf"
            )
            positions[copy_id] = export_positions(
                build, copy_id, compile_root(args.bank, build)
            )
        (stage / "positions.json").write_text(
            json.dumps(positions, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        answers = {c["copy_id"]: c["answers"] for c in copies}
        (stage / "answers.json").write_text(
            json.dumps(answers, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (stage / "config.json").write_text(
            json.dumps({"bareme": DEFAULT_BAREME}, indent=2), encoding="utf-8"
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
