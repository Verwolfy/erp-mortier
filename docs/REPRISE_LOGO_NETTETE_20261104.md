# Reprise NEXTGEN — Correction de netteté du logo (2026-11-04)

## Situation
- L'utilisateur a partagé une capture montrant encore un logo flou dans l'en-tête des documents Streamlit malgré l'ajout de `assets/nextgen_logo_hd.jpg`.
- Diagnostic dans `modules/documents/branding_images.py` : le fichier complet de 2048 × 868 px était réduit à 385 px de largeur, donc son mot-symbole était compressé puis re-rendu dans l'en-tête global.
- Décision : conserver le symbole géométrique natif et reconstituer les deux lignes du mot-symbole avec les polices de l'image de marque, à la résolution finale.

## Modifications
- `modules/documents/branding_images.py` : pour un logo HD horizontal, découpe le pictogramme NG du JPEG et l'intègre proportionnellement ; écrit séparément `NEXTGEN` et `BUILDING SOLUTIONS` en bleu marine avec des polices de taille 56 et 24. Pour les autres images, conserve le mécanisme existant.
- `tests/test_documents_nextgen.py` : vérifie la présence de pixels foncés dans deux régions distinctes (symbole et mot-symbole) avec le logo du dépôt.
- Commits `65b8ef562c3c1a82582ef0873259d0a8586fcf34` et `32eee8deb92f6b734120855ea3bac224caff15c9`.
- Aperçu local généré et inspecté : `/mnt/data/nextgen_logo_header_reworked_preview.png` (une reproduction de l'algorithme).
- Sans écriture Supabase. Projet TEST conservé en pause. Documents non émis.

## Validations à poursuivre
- GitHub Actions du commit `32eee8d` : `41828941189` tests ERP, `41828941355` audit de réconciliation. Confirmer conclusion finale et corriger les vraies erreurs, sans contourner les tests.
- Contrôle Streamlit : exporter un devis PDF puis une facture PDF depuis `Administration → Documents NEXTGEN`, vérifier logo net, pied de page, QR et pagination.
- Une vraie source SVG du logo resterait préférable pour une impression vectorielle ; le JPEG HD ne donne pas les qualités d'un fichier vectoriel.
- Toujours validation comptable algérienne avant émission réglementaire.
