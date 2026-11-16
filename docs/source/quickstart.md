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

Start from the example files — `mini-amc init` copies them into the exam folder (`bank.example.yml`, `students.example.csv`, `students.moodle.example.csv`, `runbook.md`):

```bash
mkdir my-exam && cd my-exam && mini-amc init .
```

`bank.example.yml` ([view on GitHub](https://github.com/boileaum/mini-amc/blob/main/src/mini_amc/examples/bank.example.yml)): `meta` (title, course, date) + `questions`. Two kinds:

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

Optionally, a nominative CSV links copy ids to students. Example files (copied by `mini-amc init`): [`students.example.csv`](https://github.com/boileaum/mini-amc/blob/main/src/mini_amc/examples/students.example.csv) and [`students.moodle.example.csv`](https://github.com/boileaum/mini-amc/blob/main/src/mini_amc/examples/students.moodle.example.csv):

```{literalinclude} ../../src/mini_amc/examples/students.example.csv
:language: text
:caption: students.example.csv (simple format: copy_id,name)
```

```{literalinclude} ../../src/mini_amc/examples/students.moodle.example.csv
:language: text
:caption: students.moodle.example.csv (Moodle-style export, ; separated)
```

```bash
# simple format: copy_id,name
mini-amc generate --bank bank.yml --copies 30 --seed 42 --students students.csv
# Moodle export: link column = student number, name from first/last name, delimiter auto-detected
mini-amc generate --bank bank.yml --copies 30 --seed 42 --students moodle.csv \
  --students-id-column "Numéro étudiant" --students-name-columns "Prénom,Nom"
```

## 3. Generate the copies

```bash
mini-amc generate --bank bank.example.yml --copies 30 --seed 42
```

Produces in `data/`:

- `copy_XXXX.pdf`: printable copies, seeded shuffle of questions and choices,
- `copy_XXXX.json`, `positions.json`: bubble/grade-box positions,
- `answers.json`: answer key
- `students.json` if `--students` was given.

Generation is staged: on failure, `data/` is left untouched.

Preview of the example copy (`bank.example.yml`, `students.example.csv`, copy `0001` « Alice Martin », seed 42 — corner squares, per-page QR code top right, student name in the header, MCQ bubbles, gray grader area with lettered grade boxes A/B/C for the open question):

```{figure} _static/copy.example.png
:alt: Example exam copy page generated from bank.example.yml with a fictitious student name

Copy 0001 of the example bank (page 1)
```

## 4. Print and run the exam

- Print with **no "fit to page" scaling** (it distorts the geometry).
- Check on a test copy: the 4 black corner squares and the QR code (top right) are well printed.

```{note}
Single-sided printing is recommended, not required: ink from the reverse
side can show through in the scan and skew the bubble fill measurement —
but a doubtful reading is only flagged `needs_review` for manual review,
never silently misread.
```
- Students check ONE box per single-answer MCQ (circle bubbles), several for multi-answer ones (square bubbles); open questions are left blank during the exam.
- After the exam, **before scanning**: the teacher blackens ONE lettered grade box per open question in the gray grader area (A = 0 pt, B = 1 pt, … up to `max_points`).

## 5. Scan the copies

Put the scans in `scans/` (PNG or JPG, 150-300 dpi, page preferably upright). The 4 corners and the QR code must be visible on every scan.

## 6. OMR reading

```bash
mini-amc omr    # reads scans/, writes data/omr_results.json + data/annotated/
```

Each scan gets a status: `ok` / `needs_review` (ambiguous bubbles, ungraded open question) / `unread` (unreadable). Results are aggregated per copy in `omr_results.json` (`copies` section, multi-page: `ok` / `needs_review` / `partial` / `unread`), with straightened + annotated scans in `data/annotated/`.

## 7. Review (web UI)

```bash
mini-amc web --reload    # -> http://127.0.0.1:8000/copies (reads ./data; override with --data DIR)

All commands work on the conventional `data/` directory of the current project — one common name for all exams, no per-file paths to manage (`generate`/`grades` accept `--data`/`--out`, `omr` defaults to `data/…`, `web` reads `./data` or `$MINI_AMC_DATA`).
```

JSON API (interactive docs at `/docs`):

- `GET /copies` — all copies with status, pages/questions read, corrections count, student name
- `GET /copy/{copy_id}` — per question: detected choices (`checked`, `fills`, `needs_review`), expected answer, ongoing correction, current score
- `GET /copy/{copy_id}/scan/{page}` — annotated scan image of the page
- `POST /copy/{copy_id}/correction` — `{"qid": "q1", "checked": ["B"]}` for an MCQ, `{"qid": "q5", "checked": [2]}` to override a misread grade box of an open question (empty list clears); saved to `data/corrections.json`, score recomputed. Open questions are normally graded on paper before scanning; an ungraded one shows `needs_review`.

## 8. Grades

```bash
mini-amc grades
```

Writes `data/notes.csv` (`copy_id,student,status,score,score_max`) and `data/notes_detail.csv` (`copy_id,qid,type,page,checked,correction,expected,point,needs_review`). Grading scheme v1: 1 pt per correct MCQ answer, open question = the blackened grade box value (0..max_points), no negative points; manual corrections override the OMR reading.

See the [runbook](runbook.md) for the full exam-day checklist and failure procedures, and the [API](api.md) reference.
