import argparse
import json
from pathlib import Path

import yaml


def load_bank(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    questions = data.get("questions", [])
    if not questions:
        raise ValueError("banque vide : aucune question")
    for q in questions:
        correct = [c for c in q["choices"] if c.get("correct")]
        if len(correct) != 1:
            raise ValueError(f"question {q.get('id')}: exactement 1 choix correct requis en v1")
        if len(q["choices"]) < 2:
            raise ValueError(f"question {q.get('id')}: au moins 2 choix requis")
    return data


def plan_copies(bank: dict, n_copies: int, seed: int) -> list[dict]:
    raise NotImplementedError("D3 : mélange seedé + copy_XXXX.json + answers")


def compile_copy(template_dir: Path, copy: dict, out_pdf: Path) -> None:
    raise NotImplementedError("D3 : typst compile")


def export_positions(template_dir: Path, out_json: Path) -> None:
    raise NotImplementedError("D3 : typst query -> positions.json")


def main() -> None:
    ap = argparse.ArgumentParser(description="Génère les copies d'un examen QCM (Typst)")
    ap.add_argument("--bank", type=Path, default=Path("bank.example.yml"))
    ap.add_argument("--copies", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--template", type=Path, default=Path("template"))
    ap.add_argument("--out", type=Path, default=Path("data"))
    args = ap.parse_args()

    bank = load_bank(args.bank)
    args.out.mkdir(parents=True, exist_ok=True)

    copies = plan_copies(bank, args.copies, args.seed)
    for copy in copies:
        compile_copy(args.template, copy, args.out / f"copy_{copy['copy_id']}.pdf")
    export_positions(args.template, args.out / "positions.json")
    answers = {c["copy_id"]: c["answers"] for c in copies}
    (args.out / "answers.json").write_text(
        json.dumps(answers, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
