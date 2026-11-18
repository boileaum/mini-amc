"""Write a Typst subject for tests, next to the real ``amc.typ`` prelude."""

import json
import shutil
from pathlib import Path

AMC = Path(__file__).resolve().parents[1] / "src" / "mini_amc" / "examples" / "amc.typ"


def _choice(choice: dict) -> str:
    flag = ", correct: true" if choice.get("correct") else ""
    return f"choice({json.dumps(choice['text'])}{flag})"


def _question(question: dict) -> str:
    parts = [
        f"id: {json.dumps(question['id'])}",
        f"text: {json.dumps(question['text'])}",
    ]
    if question.get("type") == "open":
        parts += ['type: "open"', f"max-points: {question['max_points']}"]
    else:
        choices = ", ".join(_choice(c) for c in question["choices"])
        parts.append(f"choices: ({choices})")
    return "    question(" + ", ".join(parts) + "),"


def write_subject(
    directory: Path,
    questions: list[dict],
    meta: dict | None = None,
    name: str = "subject.typ",
) -> Path:
    """
    Write a subject using the packaged ``amc.typ`` prelude.

    Args:
        directory: Where to write ``amc.typ`` and the subject.
        questions: Questions in the bank dict form (``id``, ``text``, and
            ``choices``, or ``type: open`` with ``max_points``).
        meta: Optional header (``title``, ``course``, ``date``).
        name: Subject file name.

    Returns:
        The subject path.
    """
    shutil.copy(AMC, directory / "amc.typ")
    meta = meta or {}
    header = "".join(
        f"  {key}: {json.dumps(meta[key])},\n"
        for key in ("title", "course", "date")
        if key in meta
    )
    body = "\n".join(_question(q) for q in questions)
    path = directory / name
    path.write_text(
        '#import "amc.typ": choice, exam, question\n\n'
        "#let bank = exam(\n"
        f"{header}"
        f"  questions: (\n{body}\n  ),\n"
        ")\n",
        encoding="utf-8",
    )
    return path
