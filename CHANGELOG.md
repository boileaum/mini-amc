# Changelog

## Unreleased

- D3 : génération complète — `plan_copies` (mélange seedé questions + choix, clés A/B/C, `answers` par copie, reproductible), `compile_copy` (build `data/build/XXXX/` : `main.typ` + `copy.json` + `qr-1..64.png`, `typst compile` → `data/copy_XXXX.pdf`), `export_positions` (`typst eval` sur `#metadata` → `data/positions.json` indexé par `copy_id`, coordonnées en pt + taille de page), `data/copy_XXXX.json` et `data/answers.json`. Validation : 3 copies seed 42, QR relu `copy:0001|page:1`, positions tombant au centre des bulles du rendu PNG.
- Tests : `tests/test_gen.py` (reproductibilité, validité du mélange, non-mutation de la banque, compile + positions, `main()` end-to-end).
- D2 : template Typst complet — `set page(background: …)` répété sur chaque page (4 carrés d'alignement 1,2 cm + QR 3 cm en haut à droite, contenu `copy:XXXX|page:N` via `qr-{page}.png`), marge haute 4,5 cm pour éviter tout chevauchement QR/texte, métadonnées `#metadata` (kind `question`/`bubble` avec page/x/y) émises pour extraction via `typst eval`, blocs de question non cassables.
- Tests : `tests/test_template.py` compile une copie de 40 questions (6 pages, 120 bulles positionnées) et vérifie le décodage QR par page.

## 0.1.0 - 2026-11-13

- Scaffold D1 : template Typst (bulles, coins, QR), squelettes `gen` / `omr` / `web`, banque exemple.
- Outillage projet exemplaire : layout `src/`, `pyproject.toml` + `uv.lock`, pre-commit (ruff, ty, pytest en pre-push), tests, docs Sphinx, CI GitHub.
