# Campagne — identification du déploiement Streamlit et visibilité des tests ignorés
Date de rédaction : 7 novembre 2026.

## Portée
Dépôt `Verwolfy/erp-mortier` sur `main`, application `app.py`, onglet
`Production & Nomenclatures > Coûts industriels`.

## Changements non sensibles
- `modules/production/cost_views.py` affiche le repère public exact
  `Version interface Coûts industriels : SOF-ERP-COUTS-20261107-PRECHECK-02`.
  L'affichage a lieu même si la lecture Supabase échoue ; aucune valeur de
  secret, token, adresse serveur privée ou identité n'est ajoutée au texte.
- `tests/test_industrial_cost_views_flows.py` vérifie les deux cas, sans
  permettre la moindre création ou validation métier.
- `.github/workflows/lot_c_tests.yml` conserve la suite complète
  `pytest` et ajoute `-rs` pour publier dans la CI les raisons explicites
  des tests ignorés. Ceci ne désactive aucun test.
- `docs/DEPLOIEMENT_STREAMLIT_VERIFICATION.md` décrit le protocole UI.

## Vérification indépendante à effectuer après publication
1. Contrôler la réussite de la CI sur la tête de PR puis sur `main`.
2. Dans l'espace de gestion de l'hébergeur, identifier l'URL exacte et vérifier
   la liaison à `Verwolfy/erp-mortier`, `main`, `app.py`. L'URL n'est pas
   démontrée par GitHub et ne doit jamais être déduite arbitrairement.
3. Une fois connecté à l'ERP, ouvrir `Production & Nomenclatures` puis
   `💰 Coûts industriels` et relever exactement le repère visible, la date,
   le domaine de l'hébergeur et le SHA `main` associé à la mise en ligne.
   Ne pas partager de capture du panneau des secrets ni des journaux bruts.
4. Vérifier séparément le statut de démarrage et les journaux d'hébergement
   sans recopier leurs secrets.
5. Contrôler dans Supabase les périodes, charges, assiettes, OF et pièces SCF
   **uniquement en lecture**. Ne pas valider une période vide ou une pièce
   fictive même si le calcul d'audit est équilibré à zéro.

## Frontière de preuve
Les CI GitHub vertes prouvent la qualité du code testé ; le repère visible
preuve la présence d'un changement UI précis dans une session de navigateur.
Ni l'un ni l'autre ne prouve à lui seul que l'hébergement est rattaché à la
bonne base ou que les workflows comptables sont homologués.

## État au 7 novembre 2026 avant confirmation de l'hébergeur
Déploiement Streamlit réel **NON VÉRIFIÉ** : URL et journaux de l'hôte
indisponibles. Périodes SCF/analytiques non clôturées, aucune donnée de
production inventée. Les écritures réglementaires officielles nécessitent
une validation par un expert-comptable algérien.
