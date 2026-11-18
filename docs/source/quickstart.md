# Quickstart

From a subject written in Typst to CSV grades, on one machine: the exam papers,
the student scans and the grades never leave it (`data/` and `scans/` are
gitignored). The two setup sections come first; the rest follows the pipeline
steps 1-8 of the README diagram, with the same numbers as the runbook. Each step
links to the page that details it.

## Setup: install

Requires Python >= 3.12, [uv](https://docs.astral.sh/uv/), and the Typst CLI pinned to v0.15.1:

```bash
uv sync --all-groups    # creates .venv, installs the project + pinned deps (uv.lock)

curl -L https://github.com/typst/typst/releases/download/v0.15.1/typst-x86_64-unknown-linux-musl.tar.xz -o /tmp/typst.tar.xz
tar -xf /tmp/typst.tar.xz -C /tmp
sudo mv /tmp/typst-x86_64-unknown-linux-musl/typst /usr/local/bin/
typst --version         # -> typst 0.15.1
```

## Setup: create the exam folder

`mini-amc init` copies a working example into the folder: the subject prelude
`amc.typ`, a ready-to-edit subject (`subject.typ`) with a second chapter and an
external code file (`q/chapter.example.typ`, `code/fizzbuzz.example.py`), two
students CSVs and the runbook. It also writes a `.gitignore` (`data/`,
`scans/`, `preview/`, `.venv/`, …), so an exam folder tracked with git never
commits local student data.

```bash
mkdir my-exam && cd my-exam && mini-amc init .
```

## Step 1: Write the subject

The subject is a Typst file, `subject.typ` (already there after `init`: replace
its questions). `amc.typ` (the prelude) turns `#choice`, `#question` and
`#exam` into plain values, and `#render(bank)` lays the draft out:

```typst
#import "amc.typ": choice, exam, question, render

#let bank = exam(
  title: "Demo exam",
  course: "Demo 101",
  date: "2026-11-12",
  questions: (
    question(
      id: "q1",
      text: "What is the capital of France?",
      choices: (
        choice("Paris", correct: true),
        choice("Lyon"),
        choice("Marseille"),
      ),
    ),
    question(
      id: "q5",
      type: "open",
      max-points: 2,
      text: "Briefly explain the French Revolution.",
    ),
  ),
)

#render(bank)   // draft PDF of the subject, without OMR markers nor QR code
```

`mini-amc` runs `typst eval` on the file and reads that same value back, so the
subject you write and the copies the students get cannot drift apart. A mistake
in a question points at your own file (line and caret) instead of the template.

A statement is Typst content: a plain string is printed verbatim, so use a
content block `[...]` as soon as it needs markup (`$math$`, `` `code` ``).

Multi-answer questions, splitting the subject over several files and pulling in
external files: [Writing the subject](subject.md).

## Step 2: Check the layout

```bash
typst watch subject.typ subject.pdf   # draft, live re-render on save
mini-amc preview --png                # the real copy (markers, QR, shuffle)
```

`mini-amc preview` renders ONE copy into the gitignored `./preview/` and never
touches `./data`; `--watch` re-renders on change. The build dir
`preview/build/0001/` is self-contained, so plain `typst compile main.typ
out.pdf` works there as a fallback.

## Step 3: Generate the copies

```bash
mini-amc generate --bank subject.typ --copies 30 --seed 42
```

Produces in `data/`:

- `copy_XXXX.pdf`: printable copies, seeded shuffle of questions and choices,
- `copy_XXXX.json`, `positions.json`: bubble/grade-box positions,
- `answers.json`: answer key,
- `config.json`: grading scheme of the exam,
- `students.json` if `--students` was given.

Generation is staged: on failure, `data/` is left untouched.

Preview of the example copy (`subject.typ`, `students.example.csv`, copy
`0001` « Alice Martin », seed 42 - corner squares, per-page QR code top right,
student name in the header, MCQ bubbles with a math formula in q3, gray grader
area with lettered grade boxes A/B/C for the open question):

```{figure} _static/copy.example.png
:alt: Example exam copy page generated from subject.typ with a fictitious student name

Copy 0001 of the example subject (page 1)
```

## Step 4: Print, exam, manual grading

- Print with **no "fit to page" scaling** (it distorts the geometry).
- Check on a test copy: the 4 black corner squares and the QR code (top right) are well printed.

```{note}
Single-sided printing is recommended, not required: ink from the reverse
side can show through in the scan and skew the bubble fill measurement -
but a doubtful reading is only flagged `needs_review` for manual review,
never silently misread.
```
- Students check ONE box per single-answer MCQ (circle bubbles), several for multi-answer ones (square bubbles); open questions are left blank during the exam.
- After the exam, **before scanning**: the teacher blackens ONE lettered grade box per open question in the gray grader area (A = 0 pt, B = 1 pt, … up to `max-points`).

## Step 5: Scan the copies

Put the scans in `scans/`, one file per page:

- **150-300 dpi**, PNG or JPG (avoid heavy JPEG compression on the QR code);
- **grayscale or color** both work (the OMR thresholds on darkness); avoid 1-bit black & white mode if it degrades the corner squares or the QR code;
- page preferably upright (the OMR straightens it anyway via the 4 corner squares, but a near-upright scan is more reliable);
- **the 4 black corner squares and the QR code (top right) must be fully visible** on every scan - a cropped corner or QR makes the page `unread`;
- avoid shadows and glare over the bubbles; no "fit to page" rescaling beyond the printer's own output.

## Step 6: OMR reading

```bash
mini-amc omr    # reads scans/, writes data/omr_results.json + data/annotated/
```

Each scan gets a status: `ok` / `needs_review` (ambiguous bubbles, ungraded open
question) / `unread` (unreadable). Results are aggregated per copy in
`omr_results.json` (`copies` section, multi-page: `ok` / `needs_review` /
`partial` / `unread`), with straightened + annotated scans in `data/annotated/`.

## Step 7: Review

```bash
mini-amc web    # -> http://127.0.0.1:8000/copies (reads ./data)
```

Only the doubtful copies need a look: the annotated scan sits next to the
detected answers, and a correction overrides the reading. What the UI shows and
its JSON API: [Review UI](review.md).

## Step 8: Grades

```bash
mini-amc grades
```

Writes `data/notes.csv` (one row per copy: `copy_id,student,status,bareme,score,score_max`)
and `data/notes_detail.csv` (one row per question). Grading schemes, student
names and the exact CSV columns: [Students and grading](students.md).

## Where to go next

- [Writing the subject](subject.md): the prelude, open questions, multi-answer, several files, external code.
- [Students and grading](students.md): nominative CSV (simple or Moodle export), grading schemes, CSV columns.
- [Review UI](review.md): statuses, annotated scans, corrections, JSON API.
- [Runbook](runbook.md): exam-day checklist and what to do when a step fails.
- [API](api.md): the Python modules.
