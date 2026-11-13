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
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    questions = data.get("questions", [])
    if not questions:
        raise ValueError("banque vide : aucune question")
    for q in questions:
        correct = [c for c in q["choices"] if c.get("correct")]
        if len(correct) != 1:
            raise ValueError(
                f"question {q.get('id')}: exactement 1 choix correct requis en v1"
            )
        if len(q["choices"]) < 2:
            raise ValueError(f"question {q.get('id')}: au moins 2 choix requis")
        if len(q["choices"]) > len(string.ascii_uppercase):
            raise ValueError(f"question {q.get('id')}: au plus 26 choix (clés A-Z)")
    return data


def plan_copies(bank: dict, n_copies: int, seed: int) -> list[dict]:
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
            "binaire `typst` introuvable dans le PATH (v0.15.1 requis, voir README)"
        )
    return typst


def compile_copy(template_dir: Path, copy: dict, out_pdf: Path) -> Path:
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
                f"copie {copy_id}: plus de {MAX_PAGES} pages "
                f"(QR qr-{MAX_PAGES + 1}.png manquant)"
            )
        raise RuntimeError(
            f"typst compile a echoue pour la copie {copy_id}:\n{proc.stderr}"
        )
    return build


def export_positions(build_dir: Path, copy_id: str) -> dict:
    _require_typst()
    proc = subprocess.run(
        ["typst", "eval", "query(metadata).map(it => it.value)", "--in", "main.typ"],
        cwd=build_dir,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"typst eval a echoue pour la copie {copy_id}:\n{proc.stderr}"
        )
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
    ap = argparse.ArgumentParser(
        description="Genere les copies d'un examen QCM (Typst)"
    )
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
