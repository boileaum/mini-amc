# Review

Only the doubtful copies need a human look. `mini-amc web` serves the review
service on `127.0.0.1:8000`, reading `./data`: a JSON API plus its interactive
Swagger page, where you can browse the copies, look at the annotated scan and
post a correction.

```bash
mini-amc web                       # http://127.0.0.1:8000/docs
mini-amc web --port 8765 --bareme amc
```

It binds to localhost only: no student data leaves the machine, and nothing is
uploaded. `--data` points the service at another exam folder, `--bareme`
overrides the scheme of `data/config.json` for the live score, `--reload` is for
development.

## Which copies to review

`GET /copies` lists every copy known from `positions.json`, with its status:

| Status | Meaning | Action |
| --- | --- | --- |
| `ok` | every page read, every bubble unambiguous | nothing |
| `needs_review` | a bubble is ambiguous, or an open question is ungraded | check, then correct |
| `partial` | some pages read, others not | check the missing pages |
| `unread` | no page could be read | check the scan, then read it again |

Each entry also gives `pages` (read) vs `pages_expected`, `questions_read` vs
`questions_total`, and `corrected`, the number of manual corrections already
saved.

A copy is `needs_review` as soon as one bubble sits between the two darkness
thresholds, or one open question has no blackened grade box. Nothing is guessed
silently: an ambiguous reading is flagged, never resolved by a coin flip.

## One copy

`GET /copy/{copy_id}` returns the copy with its questions:

```json
{
  "copy_id": "0001",
  "student": "Alice Martin",
  "status": "needs_review",
  "scans": { "1": "scans/scan-0001-1.png" },
  "questions": [
    {
      "qid": "q1",
      "type": "mcq",
      "page": 1,
      "choices": [{ "key": "A", "text": "Lyon", "correct": false }],
      "checked": ["B"],
      "fills": { "A": 0.03, "B": 0.71, "C": 0.04 },
      "needs_review": false,
      "expected": "B",
      "correction": null
    }
  ],
  "score": 7,
  "score_max": 9
}
```

`fills` is the measured ink density per bubble (0 to 1): that is what tells a
filled box from an empty one, and what makes a doubtful reading visible.
`expected` is the answer key, `correction` the manual override (`null` when
none), `score` is recomputed on every read.

`GET /copy/{copy_id}/scan/{page}` returns the annotated image of that page: the
straightened scan with the detected markers, the QR code and the bubbles
outlined, so a doubtful reading can be checked against the paper without
hunting for the file.

## Correcting

`POST /copy/{copy_id}/correction` saves one question and returns the updated
copy, score included:

```bash
curl -X POST http://127.0.0.1:8000/copy/0001/correction \
  -H 'Content-Type: application/json' \
  -d '{"qid": "q1", "checked": ["C"]}'

curl -X POST http://127.0.0.1:8000/copy/0001/correction \
  -H 'Content-Type: application/json' \
  -d '{"qid": "q5", "checked": [2]}'
```

- MCQ: `checked` is a list of choice keys; give several keys for a multi-answer
  question.
- Open question: `checked` is a list holding the graded value, an integer in
  `[0, max-points]`.
- An empty list `[]` clears the correction and falls back to the OMR reading.

Corrections are appended to `data/corrections.json` and are what
`mini-amc grades` reads, so a corrected copy scores accordingly in the CSVs.
Invalid input is rejected rather than stored: 404 for an unknown copy or
question, 422 for a key that is not on that copy or a value outside the range.

## A typical review session

```bash
mini-amc web
```

1. `GET /copies`, filter on `needs_review` and `partial`.
2. For each, `GET /copy/{copy_id}`, compare `checked` with the `fills` and the
   annotated scan.
3. Post a correction when the reading is wrong; the score updates in the
   response.
4. `mini-amc grades` once the doubtful copies are done.

A copy left `needs_review` is not lost: it is graded with what the OMR read, and
`notes.csv` keeps its status, so the doubtful rows stay visible in the export.
