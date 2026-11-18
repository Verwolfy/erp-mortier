# ERP-054 — Traitement des remarques du testeur (18 novembre 2026)

## Périmètre et preuves
Source : quatre remarques fournies par le testeur dans la conversation :
1. Calculer et afficher le PMP MP/PF.
2. Générer des documents numériques imprimables BL, OF, factures, etc.
3. Corriger le message d'erreur lors de la création d'un OF (capture précédente ERP-053).
4. État de mouvements MP/PF avec stock initial, entrées, sorties, retours, pertes, stock final, valorisé et non valorisé.

Audit direct du projet Supabase **principal** `wenydirqtmkywbxbxfal` (lecture seule ERP-054) et code GitHub `Verwolfy/erp-mortier`, `main`. Le projet test `ffuhbmcfyexsbjwhryvj` reste **INACTIVE**. **Aucune écriture SQL** ERP-054.

## Diagnostic : PMP déjà calculé, visibilité insuffisante
- La RPC `public.erp_apply_stock_movement` calcule sur entrée :
  `PMP_nouveau = (Q_avant × PMP_avant + Q_entrée × coût_entrée) / (Q_avant + Q_entrée)`.
- MP : `stock_actuel.cmp_actuel`; PF : `stock_actuel_pf.cout_revient` = **coût moyen pondéré par unité SKU**, non par KG/L. Les sorties prélèvent des lots **FIFO physiques** mais leur valeur enregistre le **PMP courant** (pas un coût FIFO).
- Le 18/11 : 115 lignes stock MP, 7 avec quantité positive, 8 avec PMP ; 146 lignes PF, 2 avec quantité positive, 4 avec PMP. Aucune ligne à quantité positive n'a de PMP NULL.
- Les stocks MP/PF non nuls se rapprochent intégralement du cumul `ENTREE - SORTIE` des journaux au moment de l'audit. Journaux : 14 mouvements MP, 6 PF, dont **1 sortie MP sans prix historique**.
- **Amélioration UI** : affichage explicite `PMP (DZD/unité)`, `PMP PF (DZD/SKU)` et `Valeur stock (DZD)` calculée `quantité × PMP` uniquement si PMP présent. Jamais de coût fictif.

## État périodique
Nouveaux fichiers :
- `modules/stocks/stock_statement.py` : calcul pur `Decimal`, reconstitution stock initial/final depuis **stock actuel + journal complet** et valorisation historique aux coûts inscrits sur les mouvements.
- `modules/stocks/views.py` : quatrième vue `📈 État périodique MP / PF`, dates inclusives, modes `Non valorisé (quantités)` et `Valorisé (DZD)`, export CSV UTF-8.
- `tests/test_erp054_stock_statement.py` : cas MP/PF, PMP, absence de prix, stock antérieur non traçable, date historique, refus incohérences.
- Adaptation des tests de navigation/callbacks pour la quatrième vue.

**Garde-fous** :
- Lecture stricte `fetch_data_strict` : droits revalidés par table, totalité de chaque journal et borne 10 000 lignes. Une lecture partielle, des mouvements non reconnus, des dates incohérentes ou des quantités impossibles bloquent le rapport.
- Le stock initial est **reconstitué**, non un inventaire physique signé. Si l'historique antérieur n'est pas traçable, les valeurs historiques initiale/finale restent NULL.
- Coûts historiques calculés uniquement à partir des prix enregistrés, jamais du PMP actuel appliqué rétroactivement. Une valeur de mouvement manquante bloque la valorisation historique concernée.
- Les colonnes `retours_clients` et `pertes` restent **NULL / non renseignées**, pas zéro. Les journaux ne connaissent que `ENTREE` et `SORTIE` ; une classification fiable requiert une évolution des flux métiers. [Issue #80](https://github.com/Verwolfy/erp-mortier/issues/80).
- Rapport de gestion **non certifié SCF**, aucune requalification de mouvements historiques.

## Documents imprimables depuis les opérations
- Les **20 modèles** administratifs PDF/DOCX préexistants sont des **brouillons non émis** ; ils ne sont pas remplacés.
- Nouveau `modules/documents/erp_print.py` : lecture **par référence exacte** et via `fetch_data_strict` (RBAC serveur), sans écriture ni numérotation, pour six types :
  1. Ordre de fabrication.
  2. Bon de livraison.
  3. Facture (**aperçu interne seulement**).
  4. Bon de réception.
  5. Commande client.
  6. Commande fournisseur.
- Chaque PDF affiche référence, date, statut, tiers/commande, lignes et montants **enregistrés**, sans inventer de prix, TVA ou quantité. Les factures portent `APERÇU INTERNE - NON VALABLE FISCALEMENT / NON ÉMIS`, les autres `COPIE DE CONSULTATION - NON SIGNÉE / NON ÉMISE`.
- `modules/documents/views.py` : `Documents administratifs NEXTGEN → Imprimer une opération ERP enregistrée (copie interne)`, saisir référence, préparer et télécharger PDF.
- `tests/test_erp054_operation_print.py` : OF, BL, BR, facture avec remise, génération PDF, refus absence de données ou de droits.
- Les factures **officielles** restent bloquées par les exigences de TVA par SKU, timbre, exonération et registre d'émission ; aucune validation fiscale n'a été effectuée. [Issue #81](https://github.com/Verwolfy/erp-mortier/issues/81), issue fiscale #76.

## OF signalé
- La capture antérieure du testeur montrait `NG-SKU-BOND-C1T-SAC-5KG` et `Unité KG/L et type de conditionnement incompatibles`.
- **ERP-053 a déjà corrigé** `unite_production='KG'` pour les 16 FENEK-BOND, avec 48/48 SKU BOND cohérents.
- **Aucune recette BOND active** : la suite attendue est `Aucune recette active pour ce produit`. Aucune formulation inventée ; validation laboratoire requise. [Issue #79](https://github.com/Verwolfy/erp-mortier/issues/79).

## Contrôles, limites, prochaines actions
- Suite de tests GitHub Actions lancée sur `main` pour ERP-054 ; vérifier la conclusion et les logs de la **dernière** exécution.
- Pas de test E2E Streamlit authentifié confirmé : navigateur TinyFish précédemment indisponible faute de crédit. Vérifier la version réellement déployée avant d'affirmer la visibilité des nouveaux écrans.
- L'émission fiscale, les retours clients, pertes et inventaires signés nécessitent spécification, droits d'approbation et migrations SQL sécurisées ; **ne pas créer de mouvements fictifs**.
- Attention technique future : la RPC SQL 002 utilise `coalesce(PMP_existant,0)` lors d'une entrée ; si un stock ancien positif perd son PMP, il faudrait refuser la nouvelle valorisation plutôt que supposer zéro. Aucune ligne actuelle à stock positif avec PMP NULL ; correction de RPC à planifier sous test de concurrence/rollback avant tout déploiement.
