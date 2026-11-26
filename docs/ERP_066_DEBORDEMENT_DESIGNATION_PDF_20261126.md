# ERP-066 — Correction du débordement des désignations PDF (26 novembre 2026)

## État final

- **CORRECTIF FUSIONNÉ sur GitHub `main`** via [PR #96](https://github.com/Verwolfy/erp-mortier/pull/96), SHA squash **`4813fb81264a900fe3ff003ced373920b8e0308d`**.
- L'image fournie montre la désignation `Mortier Colle Haute Performance C2TE - Sac 25kg` et le mot `25kg` **sous la bordure inférieure** de la colonne « Désignation » de la facture `FAC-2026-000001`.
- Le QR de repérage, les totaux HT/TVA/TTC et le montant en lettres restent présents ; leur position n'est pas modifiée dans ce correctif.
- Aucune modification de données Supabase, permission RLS, taux de TVA, émission réelle ou facturation externe.

## Cause technique reproduite

- Dans `modules/documents/erp_print.py`, le découpage calculait ses lignes à la largeur `col_width - 3` (54 mm pour une colonne de 57 mm).
- `fpdf2.multi_cell` retire ensuite **2 × `pdf.c_margin`** (~2 mm) de la largeur fournie, et re-découpe le texte une seconde fois. La ligne `Mortier Colle Haute Performance C2TE - Sac` mesurait environ **53,08 mm** avec Helvetica 7,5 pt, alors que la largeur intérieure exploitable n'était que **52 mm**.
- La hauteur du rectangle était calculée sur **2 lignes** alors que `multi_cell` dessinait **3 lignes** ; `25kg` se retrouvait en dessous du tableau.
- Reproduction géométrique locale effectuée avec fpdf2 2.8.5 et PyMuPDF : après correction, les lignes sont `Mortier Colle Haute Performance C2TE -` et `Sac 25kg` ; la boîte du second texte reste entièrement dans les limites de la cellule (test local, pas recette Streamlit).

## Implémentation

- `modules/documents/party_identity.py` : `wrap_table_cell_text` calcule la largeur utile **moins les marges internes FPDF et une tolérance** ; `draw_table_cell_text` dessine explicitement chaque ligne à des coordonnées vérifiées et refuse tout texte trop large ou hauteur insuffisante.
- `modules/documents/erp_print.py` : moteur des copies enregistrées (factures, commandes, BL, OF, BR, devis, factures fournisseurs), utilise les deux fonctions, sans retour caché.
- `modules/documents/layout_nextgen.py` : même correction pour les brouillons documentaires.
- `core/pdf_generator.py` : même correction pour le moteur historique.
- **La règle une page A4** de l'ERP-065 reste en vigueur. Si le contenu ne tient pas, l'export doit être refusé plutôt que coupé.

## Preuves de tests

- [Audit réconciliation #45855656883](https://github.com/Verwolfy/erp-mortier/actions/runs/45855656883) : **success, 3599 tests réussis, 12 avertissements**.
- [Facturation #45855656780](https://github.com/Verwolfy/erp-mortier/actions/runs/45855656780) : **success, 3599 tests réussis, 12 avertissements**.
- SHA de branche testé : `447179366417c60c8a54503f69c79dd5663173f7`.
- Nouveau test `tests/test_pdf_cell_overflow_20261126.py` : désignation exacte, mesure des deux lignes attendues et contrôle des coordonnées de texte par rapport à la bordure de la facture.
- **CI main** : distincte de la CI PR ; vérifier le succès des derniers workflows après les commits de suivi documentaire.

## Recette fonctionnelle restante

1. Vérifier le SHA de `Version ERP` en barre latérale Streamlit ; il doit inclure le commit merge `4813fb8` ou un commit ultérieur de `main`.
2. Réexporter la facture de test `FAC-2026-000001`.
3. Vérifier sur le PDF généré : `Sac 25kg` **à l'intérieur de la cellule Désignation**, page **1/1**, QR visible et scannable, totaux 1250 + 237,5 = 1487,5 DZD et montant en lettres, pied de page non couvert.
4. Contrôler aussi commande client, commande fournisseur, bon de livraison, bon de réception, ordre de fabrication et facture fournisseur sur exemples courts et références longues.
5. La capture du 26/11 montre `Statut ERP : VALIDE` sur une copie intitulée `NON ÉMIS`. La distinction entre statut métier et émission fiscale est actuellement volontaire ; vérifier la clarté de cet affichage en recette sans changer la sémantique métier.

## Prochaine session / décisions antérieures

- Lire `docs/ETAT_AVANCEMENT.md`, `docs/ERP_064_HARMONISATION_DOCUMENTS_20261126.md` et `docs/ERP_065_PDF_UNE_PAGE_20261126.md` ainsi que ce fichier.
- Le chantier de **sauvegarde externe Cloudflare R2 / B2 reste gelé** jusqu'à la fin des tests ERP, avec nouvelle autorisation explicite.
- Pour ce projet utiliser les outils connectés GitHub/Supabase et les interfaces disponibles ; **pas de TinyFish**.
- Ne pas considérer la réussite des tests CI comme une preuve du déploiement réel sur Streamlit ; la recette du PDF exporté reste à réaliser.
