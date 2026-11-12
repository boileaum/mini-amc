# Runbook — jour J (passation d'un examen)

## Prérequis

- [ ] venv activé et dépendances à jour : `pip install -r requirements.txt`
- [ ] `typst --version` → `typst 0.15.1`
- [ ] banque de questions finalisée (ex. `bank.example.yml`) : exactement 1 choix `correct: true` par question, au moins 2 choix
- [ ] `scans/` vide, prêt à recevoir les scans
- [ ] `data/` de l'examen précédent archivé (si on réutilise le dossier)

## Génération des copies

- [ ] `python3 gen/generate.py --bank <banque.yml> --copies N --seed S --out data`
- [ ] vérifier la présence de `data/copy_XXXX.pdf`, `data/positions.json`, `data/answers.json`
- [ ] chaque page des PDF porte 4 carrés noirs aux coins + 1 QR code en haut à droite (`copy:XXXX|page:N`)

## Impression

- [ ] imprimer les N copies (recto, une copie = 1 ou plusieurs pages selon le nombre de questions)
- [ ] vérifier sur une copie test : coins noirs bien imprimés, QR net, bulles non masquées

## Passation

- [ ] consigne : cocher UNE seule case par question
- [ ] ramassage des copies

## Scan

- [ ] scanner chaque copie dans `scans/` (PNG ou JPG, 150–300 dpi, page de préférence droite)
- [ ] vérifier que les 4 coins noirs et le QR sont visibles sur chaque scan

## OMR

- [ ] `python3 omr/read_scans.py --scans scans --positions data/positions.json --out data/omr_results.json`
- [ ] parcourir `data/omr_results.json` : toute copie avec le statut `a_verifier` ou `non lu` passe en relecture manuelle

## Relecture (UI web)

- [ ] `uvicorn web.app:app --reload` → http://127.0.0.1:8000/copies
- [ ] traiter une par une les copies `a_verifier` / `non lu` (scan annoté + cases détectées)
- [ ] enregistrer les corrections manuelles ; la note est recalculée à chaque correction

## Notes

- [ ] exporter `data/notes.csv` (note par copie) et `data/notes_detail.csv` (détail par question)
- [ ] archivage local : `data/` et `scans/` restent sur la machine, jamais dans le cloud

## Si une étape plante

- [ ] génération : lire le message d'erreur (banque invalide ? `typst` introuvable ? seed ?). Aucun PDF n'est écrasé tant que la génération n'a pas abouti ; `answers.json` fait foi pour la correction
- [ ] impression : si les coins ou le QR sont coupés, réduire la marge d'impression de l'imprimante (pas de « ajustage » qui déforme la géométrie)
- [ ] OMR : un scan illisible → statut `non lu`, à reprendre en relecture manuelle dans l'UI ; ne pas relancer aveuglément
- [ ] UI : si `data/omr_results.json` est absent, relancer d'abord l'étape OMR
- [ ] dernier recours : repartir d'un `data/` propre, puis relancer la génération avec le même seed (reproductible)
