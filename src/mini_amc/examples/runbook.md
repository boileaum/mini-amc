# Runbook — exam day

## Prerequisites

- [ ] exam folder scaffolded: `mini-amc init .` copies the example files here (`bank.example.yml`, `students.example.csv`, `students.moodle.example.csv`, this runbook)

- [ ] up-to-date environment: `uv sync --all-groups` (committed `uv.lock`)
- [ ] `typst --version` → `typst 0.15.1`
- [ ] finalized question bank (e.g. `bank.example.yml`): at least 1 `correct: true` choice per MCQ (several = multi-answer), at least 2 choices
- [ ] layout checked on a single copy: `mini-amc preview --png` (or `--watch` while editing)
- [ ] `scans/` empty, ready to receive the scans
- [ ] `data/` from the previous exam archived (if reusing the folder)
- [ ] dev checks pass: `uv run pre-commit run --all-files` and `uv run pre-commit run pytest --all-files --hook-stage pre-push` (plus `coverage` / `coverage-badge`)

## Copy generation (pipeline step 1)

- [ ] `mini-amc generate --bank <bank.yml> --copies N --seed S` (all commands use the conventional `./data` and `./scans`)
- [ ] optional: add `--students students.csv` to link copies to student names — stays local, never committed. Simple format `copy_id,name`, or a Moodle export with `--students-id-column "Numéro étudiant" --students-name-columns "Prénom,Nom"` (delimiter auto-detected, other columns ignored, e.g. students.moodle.example.csv). Row count must equal `--copies`; the link column values become the copy ids (printed as "Copy no." and in the QR)
- [ ] check the presence of `data/copy_XXXX.pdf`, `data/copy_XXXX.json`, `data/positions.json`, `data/answers.json` (and `data/students.json` if `--students`)
- [ ] every PDF page carries 4 black corner squares + 1 QR code at the top right (`copy:XXXX|page:N`)

## Printing (pipeline step 2)

- [ ] print the N copies (single-sided recommended but not mandatory — see the note in the quickstart; one copy = 1 or more pages depending on the number of questions)
- [ ] check on a test copy: corner squares well printed, QR sharp, bubbles not masked

## Exam (pipeline step 3)

- [ ] instructions: check ONE box per single-answer MCQ (circles), several per multi-answer (squares); open (free-text) questions are left blank during the exam
- [ ] collect the sheets

## Manual grading (on paper, before scanning) (pipeline step 4)

- [ ] for each open question of each copy, blacken ONE lettered grade box in the gray grader area (A = 0 pt, B = 1 pt, … up to `max_points`)
- [ ] an open question left ungraded will show `needs_review` after the OMR (still correctable in the review UI)

## Scanning (pipeline step 5)

- [ ] scan each sheet into `scans/` (PNG or JPG, 150–300 dpi, page preferably upright)
- [ ] check that the 4 black corners and the QR are visible on every scan

## OMR (pipeline step 6)

- [ ] `mini-amc omr` (reads `scans/`, writes `data/omr_results.json` + `data/annotated/`)
- [ ] review `data/omr_results.json` (section `copies`): any copy with status `needs_review`, `partial` (missing page) or `unread` goes to manual review
- [ ] the straightened and annotated scans (markers, QR, bubbles) are in `data/annotated/` for visual checking

## Review (web UI) (pipeline step 7)

- [ ] `mini-amc web --reload` → http://127.0.0.1:8000/copies
- [ ] go through the `needs_review` / `partial` / `unread` copies one by one (annotated scan + detected choices)
- [ ] correct the doubtful answers: `POST /copy/{id}/correction` with `{"qid": ..., "checked": ["B"]}` for an MCQ, `{"qid": ..., "checked": [value]}` to override a misread/ungraded open-question grade box (empty list clears)
- [ ] save the manual corrections; the score is recomputed on each correction (MCQ: 1 pt; open: the box value)

## Grades (pipeline step 8)

- [ ] `mini-amc grades` (scheme from `data/config.json`, override with `--bareme v1|amc`; manual corrections override the OMR reading)
- [ ] export check: `data/notes.csv` (one row per copy: `copy_id,student,status,score,score_max`) and `data/notes_detail.csv` (one row per copy/question: `copy_id,qid,type,page,checked,correction,expected,point,needs_review`)
- [ ] local archiving: `data/` and `scans/` stay on the machine, never in the cloud

## If a step fails

- [ ] generation: read the error message (invalid bank? `typst` not found? seed?). A failure leaves `data/` untouched (staged in `data/.staging`, moved into place only on success); `answers.json` is the answer key
- [ ] printing: if corners or the QR are cut off, reduce the printer margin (no "fit to page" scaling, which distorts the geometry)
- [ ] OMR: an unreadable scan → status `unread`, to be handled manually in the review UI; do not blindly re-run
- [ ] UI: if `data/omr_results.json` is missing, re-run the OMR step first
- [ ] grades: if `data/positions.json` / `answers.json` is missing, re-run generation with the same seed; an `unread` copy scores 0 until manually reviewed
- [ ] last resort: start from a clean `data/`, then re-run generation with the same seed (reproducible)
