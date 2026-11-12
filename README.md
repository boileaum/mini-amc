# mini-amc

Mini-clone d'Auto-Multiple-Choice (AMC) basé sur Typst : banque de questions YAML → copies PDF
personnalisées (mélange seedé, bulles à cocher, QR code par page) → scan → lecture OMR locale
(OpenCV) → relecture web (FastAPI) → notes CSV. Données 100 % locales, zéro package Typst externe.

## Installation

### 1. Environnement Python (venv + stack épinglée)

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

Stack épinglée : opencv-python-headless 5.0.0.93, numpy 2.5.4, pillow 13.0.0, qrcode 8.2,
PyYAML 6.0.3, fastapi 0.162.5, uvicorn 0.54.0.

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
python3 gen/generate.py --bank bank.example.yml --copies 30 --seed 42 --out data

# 2. Lecture OMR des scans placés dans scans/
python3 omr/read_scans.py --scans scans --positions data/positions.json --out data/omr_results.json

# 3. UI de relecture des copies à vérifier
uvicorn web.app:app --reload     # -> http://127.0.0.1:8000/copies
```

Voir `SCOPE.md` pour le périmètre et les décisions techniques, et `runbook.md` pour la
procédure complète du jour J (génération → impression → scan → OMR → relecture → notes).
