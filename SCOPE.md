# SCOPE — mini-amc (v1)

Mini-clone d'Auto-Multiple-Choice (AMC) basé sur Typst, développé en vibe-coding, en français.

## Périmètre v1

Inclus :

- QCM à une seule bonne réponse par question.
- Barème v1 : 1 point par bonne réponse, 0 sinon, pas de points négatifs.
- Génération de copies PDF personnalisées (mélange des questions et des choix, seedé et reproductible).
- Template Typst auto-suffisant : bulles à cocher directement sous chaque question, 4 carrés noirs d'alignement aux coins de chaque page, 1 QR code en haut à droite de chaque page.
- Lecture OMR 100 % locale des scans (OpenCV) : coins → homographie → QR → bulles.
- UI web de relecture (FastAPI) pour les cas ambigus.
- Export des notes en CSV.

Hors scope v1 :

- QCM multi-réponses.
- Barèmes avancés (points négatifs, barèmes par question, etc.).
- Export Moodle / ENT.
- Envoi de mails.
- UI riche.

## Décisions techniques (actées)

- Zéro package Typst externe (ni suiji, ni tiaoma, ni aucun package de l'Univers) :
  - le mélange aléatoire est fait en Python (seed) ;
  - les QR codes sont des PNG générés par Python (lib `qrcode`) et inclus via `#image()` ;
  - les positions des bulles seront extraites en D2/D3 via `typst query` sur `#metadata(...)`.
- Sur CHAQUE page : 4 carrés noirs d'alignement aux coins + 1 QR code (contenu texte `copy:XXXX|page:N`) en haut à droite.
- Typst CLI épinglé v0.15.1 (binaire officiel) ; `template/typst.toml` contient `compiler = "0.15.1"`.
- Syntaxe Typst 0.15 : les alignements composés s'écrivent `top + left` (pas `top-left`).
- Stack Python épinglée exactement dans `pyproject.toml` (`==`) + `uv.lock` commité : opencv-python-headless==5.0.0.93, numpy==2.5.4, pillow==13.0.0, qrcode==8.2, PyYAML==6.0.3, fastapi==0.162.5, uvicorn==0.54.0.
- Lecture du QR côté OMR avec `cv2.QRCodeDetector` (pas pyzbar, pas de dépendance système).
- Données 100 % locales : les scans de copies (données d'étudiants) ne vont jamais dans le cloud.
- Commentaires minimaux dans les fichiers `.py` et `.typ` : uniquement quand le « pourquoi » du code n'est pas évident (décision non triviale, contournement). Le « quoi » va dans le code, les décisions de conception dans `SCOPE.md` / `README.md`.

## Formats de fichiers

| Fichier | Rôle | Produit par |
| --- | --- | --- |
| `bank.example.yml` | Banque de questions (exemple) | saisie manuelle |
| `data/copy_XXXX.json` | Une copie : questions/choix mélangés, clés A/B/C… | `gen/generate.py` |
| `data/copy_XXXX.pdf` | La copie imprimable (template Typst + `copy.json` + `qr-{page}.png`) | `gen/generate.py` via `typst compile` |
| `data/build/XXXX/` | Répertoire de build Typst d'une copie (`main.typ` + `copy.json` + `qr-N.png`) | `gen/generate.py` |
| `data/positions.json` | Positions des bulles par copie (indexé par `copy_id`), extraites via `typst eval` sur `#metadata(...)` | `gen/generate.py` |
| `data/answers.json` | Réponses correctes par copie (clé de correction) | `gen/generate.py` |
| `data/omr_results.json` | Résultats OMR : `scans` (par scan : statut `ok` / `a_verifier` / `non_lu`, copy_id, page, questions) + `copies` (agrégé multi-pages par copy_id : statut `ok` / `a_verifier` / `partiel` / `non_lu`, pages, questions avec page) | `omr/read_scans.py` |
| `data/annotated/` | Scans redressés et annotés (marqueurs, QR, bulles détectées) | `omr/read_scans.py` |
| `data/notes.csv` | Note finale par copie | étape barème (D8) |
| `data/notes_detail.csv` | Détail question par question (bonne réponse cochée, attendue, point) | étape barème (D8) |

## Plan en demi-journées

| Demi-journée | Contenu |
| --- | --- |
| D1 | Cadrage + scaffold + git init |
| D2 | Template Typst complet (metadata positions, multi-page) |
| D3 | `plan_copies` seedé + `typst compile` + `positions.json` / `answers.json` |
| D4 | OMR : coins → homographie → bulles |
| D5 | QR + multi-pages + seuils |
| D6 | Tests torture |
| D7 | UI relecture FastAPI |
| D8 | Barème + CSV |
| D9 | Durcissement + runbook |
| D10 | Test end-to-end 30 copies |
| Rodage | 3 examens réels |
