# API

One page per module:

| Module | Page | What it does |
| --- | --- | --- |
| `mini_amc.cli` | [CLI](api/cli.md) | single `mini-amc` entry point, subcommands `generate` / `omr` / `grades` / `web` |
| `mini_amc.gen.generate` | [Copy generation](api/generate.md) | bank validation, seeded shuffle, Typst compilation, bubble positions |
| `mini_amc.omr.read_scans` | [OMR reading](api/omr.md) | corner markers, homography, QR, bubbles/grade boxes (OpenCV, 100% local) |
| `mini_amc.web.app` | [Review web UI](api/web.md) | FastAPI endpoints: copy list, detail, annotated scans, corrections |
| `mini_amc.grade.notes` | [Grading](api/grading.md) | bareme v1 + CSV export (`notes.csv`, `notes_detail.csv`), stdlib only |

```{toctree}
:hidden:

api/cli.md
api/generate.md
api/omr.md
api/web.md
api/grading.md
```
