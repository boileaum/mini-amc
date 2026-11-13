# mini-amc

Mini-clone d'Auto-Multiple-Choice (AMC) basé sur Typst : banque de questions YAML → copies PDF
personnalisées (mélange seedé, bulles à cocher, QR code par page) → scan → lecture OMR locale
(OpenCV) → relecture web (FastAPI) → notes CSV. Données 100 % locales, zéro package Typst externe.

## Installation

### 1. Environnement uv (Python >= 3.12, lockfile `uv.lock`)

```bash
uv sync --all-groups    # crée .venv, installe le projet + les deps épinglées + les groupes dev
```

Stack épinglée dans `pyproject.toml` (`==`) et figée par `uv.lock` : opencv-python-headless 5.0.0.93,
numpy 2.5.4, pillow 13.0.0, qrcode 8.2, PyYAML 6.0.3, fastapi 0.162.5, uvicorn 0.54.0.

### 2. Typst CLI v0.15.1 (binaire officiel, épinglé)

```bash
curl -L https://github.com/typst/typst/releases/download/v0.15.1/typst-x86_64-unknown-linux-musl.tar.xz -o /tmp/typst.tar.xz
tar -xf /tmp/typst.tar.xz -C /tmp
sudo mv /tmp/typst-x86_64-unknown-linux-musl/typst /usr/local/bin/
typst --version                   # -> typst 0.15.1
```

Sur macOS : remplacer l'archive par `typst-aarch64-apple-darwin.tar.xz` (Apple Silicon) ou
`typst-x86_64-apple-darwin.tar.xz` (Intel), ou `brew install typst` puis vérifier `typst --version`.

## Quickstart (3 commandes)

```bash
# 1. Générer les copies : data/copy_XXXX.pdf + data/positions.json + data/answers.json
mini-amc-gen --bank bank.example.yml --copies 30 --seed 42 --out data
# (équivalent : uv run python -m mini_amc.gen.generate --bank bank.example.yml ...)

# 2. Lecture OMR des scans placés dans scans/
mini-amc-omr --scans scans --positions data/positions.json --out data/omr_results.json

# 3. UI de relecture des copies à vérifier
uv run uvicorn mini_amc.web.app:app --reload     # -> http://127.0.0.1:8000/copies
```

Voir `SCOPE.md` pour le périmètre et les décisions techniques, et `runbook.md` pour la
procédure complète du jour J (génération → impression → scan → OMR → relecture → notes).
