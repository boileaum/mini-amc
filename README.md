# mini-amc

[![CI](https://github.com/boileaum/mini-amc/actions/workflows/ci.yml/badge.svg)](https://github.com/boileaum/mini-amc/actions/workflows/ci.yml)
[![docs](https://img.shields.io/badge/docs-online-3776AB?logo=readthedocs&logoColor=white)](https://boileaum.github.io/mini-amc/)
[![coverage](https://raw.githubusercontent.com/boileaum/mini-amc/main/assets/coverage.svg)](https://boileaum.github.io/mini-amc/coverage/)
[![Python](https://img.shields.io/badge/python-%3E%3D3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/boileaum/mini-amc/blob/main/LICENSE)
[![Built with Mistral Vibe](https://img.shields.io/badge/built_with-Mistral_Vibe-FF7000?logo=mistralai)](https://mistral.ai/vibe)

A mini-clone of [Auto-Multiple-Choice](https://www.auto-multiple-choice.net) (AMC) based on [Typst](https://typst.app). 100% local data (student scans never leave the machine), zero external Typst packages.

## Features

- **Everything is local**: exam papers, student scans and grades never leave your machine
- **Write the exam once**, in a YAML question bank or directly in Typst with the `amc.typ` prelude (math, code blocks, split over several files, external files pulled in with `read()`): MCQ (single-answer or multi-answer) + open questions you grade on the paper copy (blacken one lettered box in the gray grader area)
- **Print one personalized PDF copy per student** (questions and choices shuffled differently on each copy)
- **Scan the returned copies**: answers are **read automatically (OMR)**, doubtful or ambiguous cases are flagged for review
- **Review doubtful copies** in a local web UI and correct them there, with the annotated scan next to the detected answers
- **Export the grades as CSV** (per copy with the student name, and per question), ready to import into your gradebook - Moodle-export friendly

## Components

| Main component | Implementation |
| --- | --- |
| Copy generation | Python (seeded shuffle, QR PNGs) + Typst 0.15.1, zero external Typst packages |
| OMR reading (Optical Mark Recognition) | OpenCV (`cv2.QRCodeDetector`) + NumPy, 100% local |
| Review web UI | FastAPI + uvicorn |
| Grading + CSV export | Python stdlib |

## Pipeline

```mermaid
flowchart TD
  classDef exam fill:#fff3cd,stroke:#b8860b,stroke-width:3px
  classDef tool fill:#d4edda,stroke:#2e7d32,stroke-width:2px
  classDef data fill:#d1ecf1,stroke:#0c5460

  bank["bank.yml + students.csv"]:::data
  bank --> gen("<b>1</b> · mini-amc generate"):::tool
  gen --> pdf["data/copy_XXXX.pdf"]:::data
  pdf --> print("<b>2</b> · Print"):::tool
  print --> exam(["<b>3</b> · EXAM<br/>students answer on paper"]):::exam
  exam --> manual(["<b>4</b> · Manual grading<br/>on paper (optional)"]):::exam
  manual --> scan("<b>5</b> · Scan<br/>150-300 dpi, PNG/JPG<br/>corners + QR visible"):::tool
  scan --> scans["scans/"]:::data
  scans --> omr("<b>6</b> · mini-amc omr"):::tool
  omr --> res["data/omr_results.json + annotated/"]:::data
  res --> web("<b>7</b> · mini-amc web (review UI)"):::tool
  res --> grades("<b>8</b> · mini-amc grades"):::tool
  web --> corr["data/corrections.json"]:::data
  corr --> grades
  grades --> notes["data/notes.csv + notes_detail.csv"]:::data
```

Full guide: [quickstart](https://boileaum.github.io/mini-amc/quickstart.html) · exam-day checklist: [runbook](https://boileaum.github.io/mini-amc/runbook.html) · API reference: [api](https://boileaum.github.io/mini-amc/api.html) · scope and technical decisions: `SCOPE.md` in the repo.
