# Quickstart

End-to-end usage of mini-amc: from a YAML question bank to CSV grades. All data stays local (student scans never leave the machine; `data/` and `scans/` are gitignored).

## 1. Install

Requires Python >= 3.12, [uv](https://docs.astral.sh/uv/), and the Typst CLI pinned to v0.15.1:

```bash
uv sync --all-groups    # creates .venv, installs the project + pinned deps (uv.lock)

curl -L https://github.com/typst/typst/releases/download/v0.15.1/typst-x86_64-unknown-linux-musl.tar.xz -o /tmp/typst.tar.xz
tar -xf /tmp/typst.tar.xz -C /tmp
sudo mv /tmp/typst-x86_64-unknown-linux-musl/typst /usr/local/bin/
typst --version         # -> typst 0.15.1
```

## 2. Prepare the question bank

`bank.example.yml` (see the repo root): `meta` (title, course, date) + `questions`. Two kinds:

```yaml
questions:
  - id: q1                      # MCQ: choices + exactly one correct
    text: "What is the capital of France?"
    choices:
      - text: "Paris"
        correct: true
      - text: "Lyon"

  - id: q5                      # open question, graded by the teacher (0..max_points)
    type: open
    text: "Briefly explain the French Revolution."
    max_points: 2
```

Optionally, a nominative CSV links copy ids to students (see `students.example.csv` and `students.moodle.example.csv`):

```bash
# simple format: copy_id,name
mini-amc-gen --bank bank.yml --copies 30 --seed 42 --students students.csv --out data
# Moodle export: link column = student number, name from first/last name, delimiter auto-detected
mini-amc-gen --bank bank.yml --copies 30 --seed 42 --students moodle.csv \
  --students-id-column "Numéro étudiant" --students-name-columns "Prénom,Nom" --out data
```

## 3. Generate the copies

```bash
mini-amc-gen --bank bank.example.yml --copies 30 --seed 42 --out data
```

Produces in `data/`: `copy_XXXX.pdf` (printable copies, seeded shuffle of questions and choices), `copy_XXXX.json`, `positions.json` (bubble/grade-box positions), `answers.json` (answer key), and `students.json` if `--students` was given. Generation is staged: on failure, `data/` is left untouched.

## 4. Print and run the exam

- Print single-sided, **no "fit to page" scaling** (it distorts the geometry).
- Check on a test copy: the 4 black corner squares and the QR code (top right) are well printed.
- Students check ONE box per MCQ. Open questions are graded later by the teacher.

## 5. Scan the copies

Put the scans in `scans/` (PNG or JPG, 150-300 dpi, page preferably upright). The 4 corners and the QR code must be visible on every scan.

## 6. OMR reading

```bash
mini-amc-omr --scans scans --positions data/positions.json --out data/omr_results.json
```

Each scan gets a status: `ok` / `needs_review` (ambiguous bubbles, ungraded open question) / `unread` (unreadable). Results are aggregated per copy in `omr_results.json` (`copies` section, multi-page: `ok` / `needs_review` / `partial` / `unread`), with straightened + annotated scans in `data/annotated/`.

## 7. Review (web UI)

```bash
uv run uvicorn mini_amc.web.app:app --reload    # -> http://127.0.0.1:8000/copies
```

JSON API (interactive docs at `/docs`):

- `GET /copies` — all copies with status, pages/questions read, corrections count, student name
- `GET /copy/{copy_id}` — per question: detected choices (`checked`, `fills`, `needs_review`), expected answer, ongoing correction, current score
- `GET /copy/{copy_id}/scan/{page}` — annotated scan image of the page
- `POST /copy/{copy_id}/correction` — `{"qid": "q1", "checked": ["B"]}` for an MCQ, `{"qid": "q5", "checked": [2]}` for an open question (empty list clears); saved to `data/corrections.json`, score recomputed

## 8. Grades

```bash
mini-amc-grades --data data
```

Writes `data/notes.csv` (`copy_id,student,status,score,score_max`) and `data/notes_detail.csv` (`copy_id,qid,type,page,checked,correction,expected,point,needs_review`). Grading scheme v1: 1 pt per correct MCQ answer, open question = the blackened grade box value (0..max_points), no negative points; manual corrections override the OMR reading.

See the [runbook](runbook.md) for the full exam-day checklist and failure procedures, and the [API](api.md) reference.
