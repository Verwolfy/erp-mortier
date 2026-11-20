# ERP-055 — Audit des exports et harmonisation Excel / CSV / PDF

**Date : 20 novembre 2026 — dépôt privé `Verwolfy/erp-mortier`, branche `main`.**

## Objectif

Donner un téléchargement uniforme et contrôlé aux utilisateurs ERP autorisés, en conservant le format de l'entreprise NEXTGEN, les protections du référentiel fiscal et du journal SCF et la distinction **export de consultation ≠ émission officielle**.

## Inventaire des possibilités préexistantes

| Code ERP | Formats avant ERP-055 | Limite relevée |
|---|---|---|
| `modules/stocks/views.py` | État périodique CSV | Excel et PDF absents |
| `modules/documents/views.py` | 20 brouillons administratifs PDF, DOCX, JSON | Pas Excel/CSV sur les lignes ; pas de lien direct au menu ERP |
| `modules/documents/erp_print.py` | Copies PDF OF, BL, BR, facture, commandes | Pas Excel/CSV, en-tête/pied non unifiés |
| `modules/documents/product_sheets.py` | FT/FDS PDF, DOCX, JSON | Pas de version tabulaire Excel/CSV |
| `modules/admin/views.py` | Registre TVA Markdown, suivi NextGen CSV | Formats complémentaires absents |
| `modules/ventes/views.py` | Registre TVA SKU Markdown | Formats complémentaires absents |
| `modules/production/cost_views.py` | Instantanés analytiques JSON | Formats tabulaires absents |
| `core/export_scf.py` | CSV, pièces VALIDEE uniquement | Excel/PDF absents, aucune émission comptable officielle |
| Achats, CRM, RH, Finance, Production, Ventes, Stocks, Administration | Tableaux `st.dataframe` | Pas de centre d'exports homogène |

## Évolutions livrées dans GitHub

### 1. Moteur commun `core/export_formats.py`

- **Excel XLSX** : titre et raison sociale NEXTGEN, bleu marine `#0C2B50`, vert `#048B5B`, fonds clairs, entêtes lisibles, filtre, colonnes calibrées, lignes alternées, zone d'impression, gel d'entête, mention de consultation.
- **CSV** : UTF-8 avec BOM, séparateur `;`, colonnes explicites, valeurs complètes ; ce format texte ne supporte pas les couleurs/images, et ne prétend donc pas en appliquer.
- **PDF** : A4 avec les bandeaux image d'en-tête/pied `branded_images` utilisés par NEXTGEN, identité de l'entreprise, titre et mention « COPIE INTERNE » ; pagination, tableau imprimable et découpage horizontal en volets avec colonne de référence répétée.
- Protection anti-injection de formules Excel/CSV (`=`, `+`, `@`, expressions dangereuses avec `-`) et conservation des identifiants textuels avec zéros initiaux en XLSX.
- Toute donnée trop volumineuse/invalide **est refusée**, jamais exportée partiellement. Plafonds : 10 000 lignes CSV/XLSX, 250 lignes PDF, 28 colonnes, 10 000 caractères par valeur. Le PDF prévient des abréviations de cellules longues et oriente vers XLSX/CSV intégral.
- **Aucun calcul de TVA, aucune validation d'écriture SCF, aucune émission/signature**.

### 2. Centre ERP — 42 registres métier

`app.py → 📥 Centre d'exports → Registres métier`, implémenté par `modules/exports/views.py` et `core/export_catalogue.py`. Choix famille, registre, plage de dates lorsque disponible, Excel/CSV/PDF, puis téléchargement.

Familles : **Référentiels, Achats, Stocks, Production, Ventes, Finance, CRM, RH**. Les 42 registres couvrent catalogues MP/PF/SKU, fournisseurs et clients restreints, stocks, lots, mouvements, recettes et OF, achats/réceptions, ventes/livraisons et lignes de facture, règlements, CRM, salariés, congés, projets, tâches, temps.

**Permissions :** la nouvelle entrée de menu est montrée seulement aux utilisateurs dont un module métier est autorisé ; chaque fichier revalide en plus `fetch_data_strict` (droits serveur par table, lecture intégrale bornée, projection), sans clé service_role côté navigateur. Un refus de lecture arrête la préparation. Les attributs sensibles et tables sensibles sont absents du catalogue : `users`, `hash_mdp`, `permissions`, `fiches_de_paie`, logs de sécurité, journal fiscal/SCF non validé. Certains référentiels sont volontairement restreints à des colonnes non confidentielles.

Les dates métier de la base sont parfois `TEXT` avec heures : un filtre `<= AAAA-MM-JJ` en SQL écarterait les événements du soir. Le centre filtre **après lecture exhaustive plafonnée à 10 000 lignes** en comparant les dates civiles de l'intervalle inclusif. Aucun historique tronqué n'est accepté.

### 3. Documents métier et spécialisés

- Copies depuis les opérations **OF, BL, BR, commandes client/fournisseur, factures** : PDF corporate, Excel des lignes, CSV des lignes, avec référence/date/tiers et totaux enregistrés. Les factures indiquent toujours **NON VALABLE FISCALEMENT / NON ÉMISE**.
- Les **20 brouillons administratifs** conservent PDF, Word, JSON ; les **lignes** deviennent téléchargeables aussi en Excel/CSV. Les montants restent soumis au contrôle de cohérence existant.
- Les **FT/FDS** conservent PDF/Word/JSON et gagnent Excel/CSV de rubriques : **non validées**, aucune donnée technique/SGH inventée.
- **Stocks** : état périodique quantitatif/valorisé avec Excel/CSV/PDF sélectionnables, sans confondre FIFO physique et PMP.
- **Administration / Ventes TVA SKU** : exports complémentaires sous statut explicite `A_VERIFIER` ou `NON_VERIFIE`. Aucun taux ni exonération présumé ; le rôle nominatif `SECURITY_MANAGER` demeure requis en Administration.
- **Coûts analytiques** : sections de l'instantané SQL **VALIDE** en Excel/CSV/PDF, JSON original inchangé, permissions croisées Production+Finance. Ces données ne remplacent pas le SCF.
- **SCF** : la fonction `exporter_journal_scf_multiformat` ajoute XLSX/CSV/PDF **après** la validation intégrale existante de `exporter_journal_scf_csv`, qui refuse absence de droit, pièces non VALIDEE, déséquilibre, pièces fictives. Aucune interface d'émission SCF non autorisée n'a été ajoutée.

## Tests

Nouveaux tests `tests/test_erp055_exports.py` : signature et contenu XLSX, style, CSV UTF-8 et délimiteur, injection de formules, création PDF, plafonds, refus de tables/projections, revalidation des droits, fin de période horodatée, préconditions SCF. Adaptation des tests du menu `tests/test_app_security.py` et de la revue TVA `tests/test_ventes_views_security.py` au nouveau nombre de boutons.

**Ne pas conclure CI verte tant que les workflows du dernier commit `main` n'ont pas réussi.** L'interface Streamlit hébergée n'a pas encore été contrôlée par navigateur authentifié.

## Invariants non négociables

- Projet Supabase principal `wenydirqtmkywbxbxfal` **non modifié** pour ERP-055 ; aucune création de stock/OF/facture/règlement ni modification fiscale/SCF, aucune migration SQL.
- Projet test `ffuhbmcfyexsbjwhryvj` toujours inactif.
- Ne jamais considérer un fichier téléchargé comme une facture officielle, une FDS homologuée ou une pièce comptable certifiée.
- Les droits d'export sont dérivés des **lectures autorisées**, jamais d'un rôle fourni uniquement par la session.
- Le champ `statut` des documents n'est jamais promu par l'export ; aucune signature, numérotation ni journal d'émission n'est créé.

## Suite recommandée

1. Contrôler et corriger la CI sur le dernier commit de `main` (tests + audit réconciliation) ; éviter de se fier aux runs annulés par les commits successifs.
2. Après déploiement, ouvrir `https://nextgent-erp.streamlit.app/` avec une véritable session ERP, vérifier le menu **Centre d'exports** et télécharger XLSX/CSV/PDF sur des données autorisées, en testant aussi un rôle refusé. L'écart de version Streamlit est suivi par l'issue #78.
3. Effectuer la revue métier de l'homologation des modèles imprimés, distincte de l'export de consultation : numérotation, signature, archivage, validation TVA SKU, justification des coûts et SCF.
4. Pour les volumes supérieurs à 10 000 lignes, concevoir un export serveur asynchrone avec pagination temporelle contrôlée et piste d'audit avant tout changement de garde.
