# Runbook — exam day

## Prerequisites

- [ ] up-to-date environment: `uv sync --all-groups` (committed `uv.lock`)
- [ ] `typst --version` → `typst 0.15.1`
- [ ] finalized question bank (e.g. `bank.example.yml`): exactly 1 `correct: true` choice per question, at least 2 choices
- [ ] `scans/` empty, ready to receive the scans
- [ ] `data/` from the previous exam archived (if reusing the folder)

## Copy generation

- [ ] `mini-amc-gen --bank <bank.yml> --copies N --seed S --out data` (or `uv run python -m mini_amc.gen.generate …`)
- [ ] check the presence of `data/copy_XXXX.pdf`, `data/copy_XXXX.json`, `data/positions.json`, `data/answers.json`
- [ ] every PDF page carries 4 black corner squares + 1 QR code at the top right (`copy:XXXX|page:N`)

## Printing

- [ ] print the N copies (single-sided; one copy = 1 or more pages depending on the number of questions)
- [ ] check on a test copy: corner squares well printed, QR sharp, bubbles not masked

## Exam

- [ ] instructions: check ONE single box per question
- [ ] collect the sheets

## Scanning

- [ ] scan each sheet into `scans/` (PNG or JPG, 150–300 dpi, page preferably upright)
- [ ] check that the 4 black corners and the QR are visible on every scan

## OMR

- [ ] `mini-amc-omr --scans scans --positions data/positions.json --out data/omr_results.json`
- [ ] review `data/omr_results.json` (section `copies`): any copy with status `needs_review`, `partial` (missing page) or `unread` goes to manual review
- [ ] the straightened and annotated scans (markers, QR, bubbles) are in `data/annotated/` for visual checking

## Review (web UI)

- [ ] `uv run uvicorn mini_amc.web.app:app --reload` → http://127.0.0.1:8000/copies
- [ ] go through the `needs_review` / `partial` / `unread` copies one by one (annotated scan + detected choices)
- [ ] save the manual corrections; the score is recomputed on each correction

## Grades

- [ ] export `data/notes.csv` (grade per copy) and `data/notes_detail.csv` (question-by-question detail)
- [ ] local archiving: `data/` and `scans/` stay on the machine, never in the cloud

## If a step fails

- [ ] generation: read the error message (invalid bank? `typst` not found? seed?). No PDF is overwritten until generation succeeds; `answers.json` is the answer key
- [ ] printing: if corners or the QR are cut off, reduce the printer margin (no "fit to page" scaling, which distorts the geometry)
- [ ] OMR: an unreadable scan → status `unread`, to be handled manually in the review UI; do not blindly re-run
- [ ] UI: if `data/omr_results.json` is missing, re-run the OMR step first
- [ ] last resort: start from a clean `data/`, then re-run generation with the same seed (reproducible)
