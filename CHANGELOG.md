# Changelog

## Unreleased

- D5 : QR robuste + multi-pages + seuils — `read_qr` : `detectAndDecodeMulti`, variantes binarisées/upscalées, rotation de la page déduite de la position géométrique du QR (pages retournées/sideways relues correctement) ; `omr_results.json` restructuré en `{"scans": …, "copies": …}` avec agrégation multi-pages par `copy_id` (statuts `ok` / `a_verifier` / `partiel` / `non_lu`) ; seuils CLI `--seuil` (0,35) et `--seuil-gris` (0,15) : case cochée si remplissage ≥ seuil, `a_verifier` si plusieurs cochées ou trace grise, non-réponse (rien au-dessus du seuil gris) = 0 pt sans flag.
- Validation réelle : copie de 40 questions = 7 pages scannées (page 2 retournée 180°) → 7 scans `ok`, copie `ok`, 40/40 réponses conformes à `answers.json`.
- D4 : OMR géométrie + bulles — `detect_markers` (4 carrés noirs par composantes connexes, Otsu), `unwarp` (homographie vers A4 à 2 px/pt), `read_qr` (`cv2.QRCodeDetector`, `copy:XXXX|page:N`), `read_bubbles` (densité d'encre dans le disque intérieur, seuil 0,35, `a_verifier` si ≠ 1 cochée), `process_scan` (pipeline + image annotée dans `data/annotated/`), statuts `ok` / `a_verifier` / `non_lu`. Correction template : marqueurs droit/bas alignés à 0,7 cm du bord de page (les dx/dy étaient décalés d'une largeur de marqueur).
- Tests : `tests/test_omr.py` (marqueurs synthétiques, QR, bulles cochées/vides/ambigues, scan photo déformé par homographie, `main()` end-to-end). Validation réelle : scan synthétique déformé de `copy_0001` → statut `ok`, réponses retrouvées avec remplissage 1,0 vs ~0,01 ; double coche → `a_verifier` ; page blanche → `non_lu`.
- D3 : génération complète — `plan_copies` (mélange seedé questions + choix, clés A/B/C, `answers` par copie, reproductible), `compile_copy` (build `data/build/XXXX/` : `main.typ` + `copy.json` + `qr-1..64.png`, `typst compile` → `data/copy_XXXX.pdf`), `export_positions` (`typst eval` sur `#metadata` → `data/positions.json` indexé par `copy_id`, coordonnées en pt + taille de page), `data/copy_XXXX.json` et `data/answers.json`. Validation : 3 copies seed 42, QR relu `copy:0001|page:1`, positions tombant au centre des bulles du rendu PNG.
- Tests : `tests/test_gen.py` (reproductibilité, validité du mélange, non-mutation de la banque, compile + positions, `main()` end-to-end).
- D2 : template Typst complet — `set page(background: …)` répété sur chaque page (4 carrés d'alignement 1,2 cm + QR 3 cm en haut à droite, contenu `copy:XXXX|page:N` via `qr-{page}.png`), marge haute 4,5 cm pour éviter tout chevauchement QR/texte, métadonnées `#metadata` (kind `question`/`bubble` avec page/x/y) émises pour extraction via `typst eval`, blocs de question non cassables.
- Tests : `tests/test_template.py` compile une copie de 40 questions (6 pages, 120 bulles positionnées) et vérifie le décodage QR par page.

## 0.1.0 - 2026-11-13

- Scaffold D1 : template Typst (bulles, coins, QR), squelettes `gen` / `omr` / `web`, banque exemple.
- Outillage projet exemplaire : layout `src/`, `pyproject.toml` + `uv.lock`, pre-commit (ruff, ty, pytest en pre-push), tests, docs Sphinx, CI GitHub.
