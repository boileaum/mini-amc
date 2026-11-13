# mini-amc

[![CI](https://github.com/boileaum/mini-amc/actions/workflows/ci.yml/badge.svg)](https://github.com/boileaum/mini-amc/actions/workflows/ci.yml)
[![pages](https://github.com/boileaum/mini-amc/actions/workflows/pages.yml/badge.svg)](https://github.com/boileaum/mini-amc/actions/workflows/pages.yml)
[![Python](https://img.shields.io/badge/python-%3E%3D3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/boileaum/mini-amc/blob/main/LICENSE)
[![Built with Mistral Vibe](https://img.shields.io/badge/built_with-Mistral_Vibe-FF7000?logo=mistralai)](https://mistral.ai/vibe)

A mini-clone of Auto-Multiple-Choice (AMC) based on Typst: YAML question bank → personalized PDF copies (seeded shuffle, check bubbles, per-page QR code) → scan → local OMR reading (OpenCV) → web review (FastAPI) → CSV grades. 100% local data, zero external Typst packages. Everything in English.

Developed by vibe-coding with [Mistral Vibe](https://mistral.ai/vibe) (every commit carries the `Co-Authored-By: Mistral Vibe` trailer).

## Installation

### 1. uv environment (Python >= 3.12, committed `uv.lock`)

```bash
uv sync --all-groups    # creates .venv, installs the project + pinned deps + dev groups
```

Pinned stack in `pyproject.toml` (`==`) and frozen by `uv.lock`: opencv-python-headless 5.0.0.93,
numpy 2.5.4, pillow 13.0.0, qrcode 8.2, PyYAML 6.0.3, fastapi 0.162.5, uvicorn 0.54.0.

### 2. Typst CLI v0.15.1 (official binary, pinned)

```bash
curl -L https://github.com/typst/typst/releases/download/v0.15.1/typst-x86_64-unknown-linux-musl.tar.xz -o /tmp/typst.tar.xz
tar -xf /tmp/typst.tar.xz -C /tmp
sudo mv /tmp/typst-x86_64-unknown-linux-musl/typst /usr/local/bin/
typst --version                   # -> typst 0.15.1
```

On macOS: replace the archive with `typst-aarch64-apple-darwin.tar.xz` (Apple Silicon) or
`typst-x86_64-apple-darwin.tar.xz` (Intel), or `brew install typst` then check `typst --version`.

## Quickstart (3 commands)

```bash
# 1. Generate the copies: data/copy_XXXX.pdf + data/positions.json + data/answers.json
mini-amc-gen --bank bank.example.yml --copies 30 --seed 42 --out data
# (equivalent: uv run python -m mini_amc.gen.generate --bank bank.example.yml ...)

# 2. OMR reading of the scans placed in scans/
mini-amc-omr --scans scans --positions data/positions.json --out data/omr_results.json

# 3. Review UI for the copies to check
uv run uvicorn mini_amc.web.app:app --reload     # -> http://127.0.0.1:8000/copies
```

See `SCOPE.md` for the scope and technical decisions, and `runbook.md` for the full
exam-day procedure (generation → printing → scan → OMR → review → grades).
