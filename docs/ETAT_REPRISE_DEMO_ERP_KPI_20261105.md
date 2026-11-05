# ERP — Jeu de données fictives et retour arrière (5 novembre 2026)

## Périmètre et objectif

Jeu de données **strictement fictives** chargé sur la base principale Supabase `erp-mortier` (`wenydirqtmkywbxbxfal`) à la demande du propriétaire pour exercer l'ERP et « Tableaux de bord & KPIs ».

- **78 lignes créées, dans 53 tables** ; identifiants `DEMO26_*`, deux UUID explicitement déterministes (`90000000-0026-4026-8026-000000000001/0002`), deux comptes SCF `41199926` et `70199926`, et trois ID numériques négatifs `-260001/-260002/-260003`.
- Aucun `UPDATE` des données existantes ; aucune modification de schéma, de paramètres réglementaires, de rôles, d'utilisateurs, de droits ou de RLS.
- Certaines factures et certains règlements fictifs portent `VALIDE` pour permettre les agrégations du tableau de bord. **Ce ne sont ni des ventes ni des paiements réels. Ne jamais utiliser pour la fiscalité, la comptabilité officielle ou des relances.**
- Les paies V2 et pièces SCF fictives sont laissées en `PREPARE` / `BROUILLON` : pas de validation légale, pas de taux sociaux inventés.
- La qualification TVA des SKU fictifs reste `A_VALIDER` (aucune affirmation juridique).
- Les 37 autres tables ne sont **pas** alimentées : elles comprennent en particulier gestion d'authentification, journaux, tables d'opérations techniques/outbox, paramètres et données de publication du site ; les peupler artificiellement fausserait ou pourrait déclencher des opérations sensibles.

## Scripts versionnés

1. `sql/demo/20261105_seed_erp_kpi_FICTIF.sql` — insertions transactionnelles, garde de collisions avec les clés existantes, données déterministes et taux de TVA **lu dans la table de paramètres**, jamais inventé.
2. `sql/demo/20261105_rollback_erp_kpi_FICTIF.sql` — supprime **uniquement** les identifiants exacts du jeu de test, dans l'ordre inverse des dépendances, sans `CASCADE`. **Ce script n'a pas été exécuté en production.**
3. `sql/demo/20261105_verification_erp_kpi_FICTIF.sql` — contrôles de volume, statuts, cohérence de scénarios et valeurs KPI attendues.

### Preuves d'exécution

- Essai initial à blanc refusé : `GENERATED ALWAYS` sur `ligne_id` ; aucun commit à cette étape.
- Candidat corrigé avec `OVERRIDING SYSTEM VALUE` pour les lignes à identifiants explicitement réservés.
- **Dry-run insertion** dans une transaction suivie de `ROLLBACK` : `DRY_RUN_OK`.
- **Dry-run insertion puis script de retour arrière**, suivi de `ROLLBACK` : 0 client, 0 facture, 0 pièce SCF, 0 bulletin test restant dans la transaction.
- **Insertion réelle** en transaction `BEGIN/COMMIT` : commande Supabase acceptée.
- **Lecture après insertion** : 53 tables contenant les lignes attendues, total **78**, aucune table attendue à zéro.
- **Script de vérification réel** : `CONTROLES_DEMO_OK`.

### Échantillon des valeurs KPI de démonstration isolées par identifiants

| Indicateur simulé | Valeur |
|---|---:|
| CA HT de novembre 2026 | 16 000 DZD |
| Impayé simulé avec plus de 30 jours de retard | 9 900 DZD |
| Commandes achats fictives en retard | 1 |
| Encaissements fictifs | 3 000 DZD |
| Décaissements fictifs | 5 000 DZD |
| Pipeline CRM pondéré fictif | 300 000 DZD |
| Rejets qualité fictifs | 1 |
| Congés fictifs en attente | 1 |
| Valeur de stocks MP fictifs | 63 000 DZD |
| Valeur de stocks PF fictifs | 270 000 DZD |
| Pièces SCF fictives brouillon | 1 |
| Bulletins V2 fictifs préparés | 1 |

Ces valeurs sont la **contribution du jeu de test** ; le tableau de bord peut afficher d'autres chiffres lorsqu'il additionne les lignes existantes.

## Instructions de retour arrière

1. Suspendre les manipulations des enregistrements `DEMO26_*` pendant le retrait. Vérifier qu'aucune ligne créée ultérieurement ne les référence.
2. Exécuter `sql/demo/20261105_rollback_erp_kpi_FICTIF.sql` sur la base **principale**, dans son intégralité. La transaction est atomique : la moindre FK bloquante doit empêcher le retrait ; ne pas supprimer les données réelles liées, ne pas forcer `CASCADE`.
3. Confirmer 0 clé `DEMO26_*` dans les 53 tables, 0 UUID de simulation et 0 ID numérique réservé. Les données antérieures au test doivent rester intactes.

**Limite du rollback :** il restaure les lignes insérées et ne constitue **pas** une sauvegarde complète PostgreSQL. Si des utilisateurs modifient d'autres données en s'appuyant sur ce jeu de test, leurs changements supplémentaires ne seront pas automatiquement annulés. Ne pas prétendre à un retour exact après de telles manipulations.

## Travaux restant à faire

- Vérifier les workflows CI du dernier commit.
- Tester le rendu réel de chaque panneau Streamlit « Tableaux de bord & KPIs » avec un compte disposant des permissions correspondantes : les **calculs SQL** ont été contrôlés, pas le rendu navigateur ni la totalité des chemins d'exécution applicatifs.
- Si des parcours fonctionnels réclament davantage de scénarios, compléter le jeu par **un deuxième lot distinct**, avec script de retour arrière indépendant, sans injecter des données juridiques, des identités, des certifications ou des écritures irréversibles.
- Écarter les données `DEMO26_*` des exports, relances et déclarations réels tant qu'elles sont dans la base principale.
- Validation d'un expert-comptable algérien indispensable avant toute exploitation réglementaire.

## Reprise du 5 novembre — vérifications du Dashboard après alimentation

- CI de la publication du jeu fictif (commit `888b9655`) : **deux workflows réussis** ([audit](https://github.com/Verwolfy/erp-mortier/actions/runs/42073898871), [lot C](https://github.com/Verwolfy/erp-mortier/actions/runs/42073898843)).
- Les statuts `factures` (3 lignes), `reglements` (2), `commandes_achats` (3), `pipeline` (3) et `employes` (12) ont été contrôlés avec les valeurs admises par `modules/dashboards/service.py` : **aucun statut invalide**.
- **Défaut P&L identifié puis corrigé** dans `modules/dashboards/views.py` : la fin de période proposée était le jour courant, mais `payroll_net_for_period` exige un mois complet lorsque des fiches de paie sont présentes. La fin par défaut correspond désormais à la **fin du mois courant** via `_current_month_end`. Début conservé au premier du mois courant. L'utilisateur peut toujours choisir d'autres dates, avec l'exigence de mois complets si des paies existent.
- `tests/test_dashboard_pnl_month_default.py` ajouté : contrôle novembre 2026, décembre, février bissextile et non bissextile et utilisation dans le widget.
- Commits : `e05169c3` (correctif) et `4908b673` (tests). Les résultats GitHub Actions de ces commits restent à confirmer.
- Aucun ajout, retrait ou changement des **78 lignes fictives** dans cette reprise. Le rollback `sql/demo/20261105_rollback_erp_kpi_FICTIF.sql` reste disponible et **non exécuté**.
- **Limite non résolue :** faute de session Streamlit ERP authentifiée, aucun parcours de rendu visuel réel des 9 onglets n'a été effectué. Les tests automatisés et contrôles SQL ne doivent pas être présentés comme une validation navigateur.
- Prochaines priorités : vérifier les CI du dernier commit, tester les 9 onglets en session autorisée, repérer les écrans qui exigent plus de scénarios ; enrichir uniquement avec des lots identifiés et un rollback indépendant. Maintenir l'exclusion des identifiants `DEMO26_*` de tout export officiel, relance ou reporting de production.

## Contrôle complémentaire du 5 novembre — intégrité de la démonstration

- GitHub Actions du commit `888b9655` : les deux workflows principaux étaient `success`.
- Audit en lecture seule des sources KPI : 107 valeurs de coûts/quantités MP et 142 PF initialement signalées comme `NULL` sur les stocks existants ; une vérification affinée établit cependant **0 quantité nulle** et **0 coût nul pour les stocks strictement positifs**, donc pas de justification à inventer des coûts. Les lignes avec stock nul et coût indéterminé demeurent acceptables pour `stock_value`.
- Le contrôle des dates/états des factures, règlements, commandes, pipeline, RH et OF n'a signalé aucune anomalie ; une date manquante de contrôle qualité hors scénario de test reste à analyser sans la remplir artificiellement.
- Anomalie réelle du jeu DEMO : facture `DEMO26_FAC1` initialement `montant_paye=0` malgré un lettrage fictif de 3 000 DZD ; `DEMO26_FAC2` initialement `montant_paye=2 000` sans lettrage. Les seules deux lignes **fictives** ont été corrigées en transaction vers 3 000 et 0 respectivement (aucune ligne réelle modifiée).
- Le seed GitHub `sql/demo/20261105_seed_erp_kpi_FICTIF.sql` et le vérificateur `sql/demo/20261105_verification_erp_kpi_FICTIF.sql` ont été alignés. Résultat du contrôle SQL en production après modification : `CONTROLES_DEMO_OK`.
- Le montant de la créance fictive dépassant 30 jours est désormais **11 900 DZD**, en remplacement des 9 900 DZD indiqués dans le tableau antérieur du présent document. Les rapports réels mélangent potentiellement ces contributions démo avec d'autres données.
- Le script de rollback original reste applicable : il supprime ces deux factures par identifiant, indépendamment de `montant_paye`. Il **n'a pas été exécuté**.
- Le correctif P&L a été publié (`e05169c3`) avec tests (`4908b673`). Les tests de la toute dernière branche principale doivent être confirmés après les commits de documentation/données.
- Aucune validation visuelle des neuf onglets Streamlit depuis une session connectée n'est attestée.

## Vérification des neuf familles KPI — données fictives isolées

Comparaison réalisée en SQL **sur Supabase principale**, après correction des montants payés fictifs. Les valeurs sont calculées uniquement à partir des identifiants DEMO et constituent des contrôles de cohérence des agrégats **pas un test de rendu Streamlit ni du RBAC**.

| Onglet | Mesure contrôlée | Observé | Attendu | Verdict |
|---|---|---:|---:|---|
| Direction | Facturation HT novembre | 16 000 DZD | 16 000 DZD | OK |
| Rentabilité P&L | Solde estimatif novembre, y compris coûts, paiement OPEX et net fictif | -49 000 DZD | -49 000 DZD | OK |
| Ventes | Factures clients validées novembre | 1 | 1 | OK |
| Achats | Montant commandes novembre | 80 000 DZD | 80 000 DZD | OK |
| Stocks | Valeur MP + PF démo | 333 000 DZD | 333 000 DZD | OK |
| Production | OF planifiés en novembre | 2 | 2 | OK |
| CRM | Pipeline pondéré ouvert | 300 000 DZD | 300 000 DZD | OK |
| RH | Effectifs actifs fictifs | 2 | 2 | OK |
| Finance | Encaissements fictifs validés novembre | 3 000 DZD | 3 000 DZD | OK |

**9/9 contrôles SQL = OK**. La requête ne prétend pas reproduire intégralement les neuf fonctions Python ; elle vérifie une mesure représentative par panneau. Les agrégats affichés pour toute la base peuvent différer des seuls agrégats fictifs. Le test interactif Streamlit reste non réalisé.

## Contrats Python des neuf modules Dashboard — 2026-11-05

- Nouvelle suite `tests/test_dashboard_nine_demo_scenarios.py`, construite avec des tables en mémoire et des lectures `fetch_data` / `fetch_data_by_date_range` remplacées, **sans accès ni mutation Supabase**.
- Les **neuf fonctions Python réelles** du module `modules.dashboards.service` sont exercées : Direction, Rentabilité P&L, Ventes, Achats, Stocks, Production, CRM, RH, Finance.
- Valeurs attendues : Direction (CA HT 16 000, trésorerie 1 023 000, impayés > 30j 11 900, une alerte de stock), P&L -49 000, Ventes 1 facture, Achats 80 000 et 1 retard, Stocks 63 000 + 270 000, Production 2 OF / rejet 100 %, CRM 300 000 / conversion 50 %, RH 2 actifs / 1 congé, Finance +3 000 / -5 000 / lettrage 100 %.
- Dans ce jeu, la facture du 1er septembre 2026 échue le 30 septembre 2026 présente **36 jours de retard au 5 novembre 2026** et relève de la tranche **31 à 60 jours** ; le test le vérifie explicitement.
- Commits : `ab787d70` (suite créée) et `224419ec` (attente de tranche ajustée).
- Les résultats CI des nouveaux tests doivent être contrôlés ; aucune validation Streamlit interactive ni nouvelle écriture dans Supabase ne sont attestées.
- Le rollback SQL des 78 lignes fictives **n'a pas changé**, et ne doit pas être exécuté avant la fin des essais.

## Vérification du 5 novembre — CI, permissions et réversibilité

- Les workflows GitHub du commit `86fe6ce1` ont tous deux terminé en `success` : [suite de tests](https://github.com/Verwolfy/erp-mortier/actions/runs/42076603179) et [audit de réconciliation](https://github.com/Verwolfy/erp-mortier/actions/runs/42076603144).
- Lecture seule du référentiel `public.permissions` de Supabase principale : **9 entrées, toutes pour `ADMIN`**, couvrant les neuf modules métier dont `Dashboards`, lecture et écriture à `OUI`. **Aucun autre rôle n'a une permission dédiée actuellement**. Le module Streamlit vérifie `has_permission(role, 'Dashboards', 'lecture')` avant de créer les onglets ; les neuf onglets sont enveloppés dans des sections `read_section`, et le rendu global dans `dashboard_read_scope`.
- La présente vérification ne prouve pas une authentification bout en bout sur l'application Streamlit. Ne pas ajouter d'utilisateurs ou de privilèges de démonstration sans revue de sécurité.
- Nouveau contrat statique `tests/test_demo_rollback_contract.py` ajouté au commit `7e1c49c3` : les 53 tables du seed doivent correspondre exactement et en ordre inverse aux 53 commandes de suppression, chaque suppression reste bornée aux identifiants de la démo, sans `CASCADE` ni DDL/DML additionnels. Le test ne supprime aucune donnée.
- Les 78 données fictives demeurent dans Supabase principale. Le script de rollback n'a pas été exécuté. Tests CI de la nouvelle modification à vérifier.
- Reste à faire : validation visuelle des neuf onglets avec une session Streamlit réellement habilitée, puis éventuel élargissement des scénarios avec **lot séparé et rollback distinct**. Ne pas déclencher de déclaration/export ou relance réelle depuis les documents fictifs.

## Validation finale du rollback à blanc sur la base déjà alimentée

- CI `50e50108` : [suite ERP](https://github.com/Verwolfy/erp-mortier/actions/runs/42077081862) et [audit sans modification](https://github.com/Verwolfy/erp-mortier/actions/runs/42077082215), conclusions `success`.
- Le **script de rollback versionné réel**, `sql/demo/20261105_rollback_erp_kpi_FICTIF.sql`, a été relu sur `main` puis **exécuté à blanc** sur la base principale déjà alimentée : son `COMMIT` final a été remplacé, pour cet essai uniquement, par une vérification SQL des suppressions et `ROLLBACK`. Résultat interne à la transaction : **0 client, 0 facture, 0 pièce SCF, 0 bulletin V2** parmi les identifiants fictifs testés, sans erreur SQL ni FK.
- Lecture après `ROLLBACK`, dans une nouvelle requête : **2 clients fictifs, 2 factures fictives, 1 pièce SCF brouillon, 1 bulletin V2 préparé, 3 opportunités CRM** sont toujours présents. La transaction d'essai a donc bien été annulée.
- **Ne pas confondre cette preuve avec un retour arrière définitif :** les **78 lignes fictives** sont toujours présentes dans Supabase et le rollback versionné n'a pas été exécuté jusqu'au `COMMIT` en production.
- Cette preuve concerne le retrait des identifiants présents au moment du test ; elle ne garantit pas le retrait si des utilisateurs créent ensuite de nouvelles dépendances externes, ni l'annulation de modifications extérieures au jeu fictif.
- La validation **visuelle et interactive** des neuf onglets dans une session Streamlit habilitée reste non effectuée. Aucun compte réel n'a été créé ni droit modifié pour forcer cette étape.
