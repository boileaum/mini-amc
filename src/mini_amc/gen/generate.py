"""QCM exam copy generation: seeded shuffle, Typst compilation, bubble positions."""

import argparse
import json
import random
import shutil
import string
import subprocess
from pathlib import Path

import qrcode
import yaml

MAX_PAGES = 64
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
        ValueError: Empty bank, or a question without exactly one
            ``correct`` choice, or choice count outside [2, 26].
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    questions = data.get("questions", [])
    if not questions:
        raise ValueError("empty bank: no questions")
    for q in questions:
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


def plan_copies(bank: dict, n_copies: int, seed: int) -> list[dict]:
    """
    Plan the copies: seeded shuffle of questions and choices.

    The bank is not mutated. Each copy gets keys A, B, C… reassigned
    according to the shuffled order, and an ``answers`` dict
    (``qid`` -> correct key).

    Args:
        bank: Bank validated by :func:`load_bank`.
        n_copies: Number of copies (ids ``0001``, ``0002``…).
        seed: Random generator seed (reproducibility).

    Returns:
        List of copies, each with ``copy_id``, ``meta``, ``questions``
        and ``answers``.
    """
    rng = random.Random(seed)
    questions = bank["questions"]
    copies = []
    for i in range(1, n_copies + 1):
        copy_id = f"{i:04d}"
        answers = {}
        copy_questions = []
        for q in rng.sample(questions, len(questions)):
            choices = rng.sample(q["choices"], len(q["choices"]))
            copy_choices = []
            for c, key in zip(choices, string.ascii_uppercase, strict=False):
                copy_choices.append(
                    {"key": key, "text": c["text"], "correct": bool(c.get("correct"))}
                )
                if c.get("correct"):
                    answers[q["id"]] = key
            copy_questions.append(
                {"id": q["id"], "text": q["text"], "choices": copy_choices}
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
        Dict with ``copy_id``, ``page`` (``w_pt``/``h_pt``), ``questions``
        and ``bubbles`` (each with ``qid``, ``page``, ``x_pt``, ``y_pt``,
        plus ``key`` for bubbles).

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
    }


def main() -> None:
    """
    CLI entry point ``mini-amc-gen``.

    Produces in ``--out``: ``copy_XXXX.json``, ``copy_XXXX.pdf``,
    ``positions.json`` (indexed by copy_id) and ``answers.json``.
    """
    ap = argparse.ArgumentParser(description="Generate QCM exam copies (Typst)")
    ap.add_argument("--bank", type=Path, default=Path("bank.example.yml"))
    ap.add_argument("--copies", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--template", type=Path, default=Path("template"))
    ap.add_argument("--out", type=Path, default=Path("data"))
    args = ap.parse_args()

    bank = load_bank(args.bank)
    args.out.mkdir(parents=True, exist_ok=True)

    copies = plan_copies(bank, args.copies, args.seed)
    positions = {}
    for copy in copies:
        copy_id = copy["copy_id"]
        copy_json = {k: v for k, v in copy.items() if k != "answers"}
        (args.out / f"copy_{copy_id}.json").write_text(
            json.dumps(copy_json, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        build = compile_copy(args.template, copy_json, args.out / f"copy_{copy_id}.pdf")
        positions[copy_id] = export_positions(build, copy_id)
    (args.out / "positions.json").write_text(
        json.dumps(positions, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    answers = {c["copy_id"]: c["answers"] for c in copies}
    (args.out / "answers.json").write_text(
        json.dumps(answers, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
