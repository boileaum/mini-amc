# Runbook - exam day

Checklist for exam day. Steps 1-8 match the pipeline diagram (README) and the quickstart headings; explanations and options are in the [quickstart](https://boileaum.github.io/mini-amc/quickstart.html).

| Step | Action | Command | Produces |
| --- | --- | --- | --- |
| 1 | Generate the copies | `mini-amc generate --bank bank.yml --copies N --seed S [--students students.csv]` | `data/copy_XXXX.pdf`, `positions.json`, `answers.json`, … |
| 2 | Print | printer, no "fit to page" scaling | paper copies (corners + QR on every page) |
| 3 | Exam | - | students check the bubbles on paper |
| 4 | Manual grading (on paper) | blacken ONE lettered grade box per open question | grade boxes in the gray grader area |
| 5 | Scan | scanner: 150-300 dpi, PNG/JPG, grayscale or color | `scans/` (one file per page) |
| 6 | OMR | `mini-amc omr` | `data/omr_results.json` + `data/annotated/` |
| 7 | Review | `mini-amc web --reload` → http://127.0.0.1:8000/copies | `data/corrections.json` |
| 8 | Grades | `mini-amc grades` | `data/notes.csv` + `data/notes_detail.csv` |

## Prerequisites (setup)

- [ ] exam folder scaffolded: `mini-amc init .` (example files + `.gitignore`: `data/`, `scans/`, `preview/` are never committed)
- [ ] up-to-date environment: `uv sync --all-groups` (committed `uv.lock`)
- [ ] `typst --version` → `typst 0.15.1`
- [ ] finalized question bank (`bank.example.yml`, or a Typst subject `subject.typ`): at least 1 `correct: true` per MCQ, at least 2 choices
- [ ] layout checked on one copy: `mini-amc preview --png` (or `--watch` while editing) - quickstart, Step 1
- [ ] `scans/` empty; previous `data/` archived if reusing the folder

## Step 1: Copy generation

- [ ] `mini-amc generate --bank <bank.yml|subject.typ> --copies N --seed S` (conventional `./data` and `./scans`)
- [ ] optional `--students students.csv` to link copies to student names (quickstart, Setup): simple `copy_id,name`, or a Moodle export with `--students-id-column` / `--students-name-columns`; row count must equal `--copies`
- [ ] check `data/copy_XXXX.pdf`, `copy_XXXX.json`, `positions.json`, `answers.json` (and `students.json` if `--students`)
- [ ] every PDF page carries 4 black corner squares + 1 QR code top right (`copy:XXXX|page:N`)

## Step 2: Printing

- [ ] print the N copies, no "fit to page" scaling (single-sided recommended, not mandatory - quickstart, Steps 2-4)
- [ ] on a test copy: corner squares well printed, QR sharp, bubbles not masked

## Step 3: Exam

- [ ] instructions: ONE box per single-answer MCQ (circles), several per multi-answer (squares); open questions left blank
- [ ] collect the sheets

## Step 4: Manual grading (on paper, before scanning)

- [ ] per open question and copy: blacken ONE lettered grade box in the gray grader area (A = 0 pt, B = 1 pt, … up to `max_points`)
- [ ] an ungraded open question shows `needs_review` after the OMR (still correctable in the review UI)

## Step 5: Scanning

- [ ] one file per page into `scans/`: PNG/JPG, 150-300 dpi, grayscale or color (avoid 1-bit B/W if it degrades corners/QR), page preferably upright
- [ ] the 4 black corners and the QR fully visible on every scan

## Step 6: OMR

- [ ] `mini-amc omr` (reads `scans/`, writes `data/omr_results.json` + `data/annotated/`)
- [ ] in `omr_results.json` (`copies` section): every `needs_review` / `partial` / `unread` copy goes to manual review
- [ ] annotated scans (markers, QR, bubbles) in `data/annotated/` for visual checking

## Step 7: Review (web UI)

- [ ] `mini-amc web --reload` → http://127.0.0.1:8000/copies
- [ ] go through the `needs_review` / `partial` / `unread` copies (annotated scan + detected choices)
- [ ] correct doubtful answers: `POST /copy/{id}/correction` with `{"qid": ..., "checked": ["B"]}` (MCQ) or `{"qid": ..., "checked": [value]}` (grade-box override; empty list clears) - the score is recomputed on each correction

## Step 8: Grades

- [ ] `mini-amc grades` (scheme from `data/config.json`, `--bareme v1|amc` overrides; corrections override the OMR reading)
- [ ] check `data/notes.csv` (`copy_id,student,status,score,score_max`) and `data/notes_detail.csv` (per copy/question)
- [ ] `data/` and `scans/` stay on the machine, never in the cloud

## If a step fails

- [ ] generation: read the error (invalid bank? `typst` missing? seed?); a failure leaves `data/` untouched (staged in `data/.staging`); `answers.json` is the answer key
- [ ] printing: corners/QR cut off → reduce the printer margin (no "fit to page")
- [ ] OMR: an unreadable scan → `unread`, handle it in the review UI; do not blindly re-run
- [ ] UI: missing `data/omr_results.json` → re-run step 6 first
- [ ] grades: missing `positions.json` / `answers.json` → re-run step 1 with the same seed; an `unread` copy scores 0 until reviewed
- [ ] last resort: clean `data/`, re-run step 1 with the same seed (reproducible)
