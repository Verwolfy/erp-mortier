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

## Validation intégrale à blanc du jeu démo (2026-11-05)

- GitHub Actions du commit `1b78e0c8` : [tests ERP](https://github.com/Verwolfy/erp-mortier/actions/runs/42078313193) et [audit de réconciliation](https://github.com/Verwolfy/erp-mortier/actions/runs/42078313098), tous deux `success`.
- Test supplémentaire en base Supabase principale effectué **dans une seule transaction** : (1) lecture de **53 prédicats exacts**, extraits du script `sql/demo/20261105_rollback_erp_kpi_FICTIF.sql`, confirmant **78 lignes** avant opération ; (2) exécution à blanc des **53 DELETE** sans erreur FK ; (3) relecture des mêmes 53 prédicats confirmant **0 ligne** après suppressions dans la transaction ; (4) exécution finale de **ROLLBACK** (et non COMMIT). Résultat `53 tables_controlees, 78 lignes_supprimees_dans_transaction, ROLLBACK_IMMEDIAT`.
- Une lecture ultérieure, hors transaction d'essai, confirme la persistance de **2 clients, 2 factures, 3 opportunités CRM et 1 pièce SCF fictifs**. Aucune suppression définitive n'a eu lieu.
- Le **script SQL de rollback versionné n'a pas été modifié**. Sa réversibilité est prouvée pour l'état présent des 53 tables, sous réserve d'absence de nouvelles dépendances utilisateurs après ce contrôle.
- Limite persistante : pas de validation visuelle des neuf onglets en session Streamlit connectée ; les tests GitHub sont automatisés et reposent sur des données locales simulées, pas sur un navigateur ERP authentifié. Ne pas déclarer ce parcours réalisé.
- Prochaine priorité : vérifier déploiement accessible et effectuer navigation autorisée sans fabriquer de session ni modifier les permissions ; conserver les données `DEMO26_*` exclues des déclarations et transactions réelles.

## Sécurisation des relances automatiques (2026-11-05)

- Les deux workflows du commit `a68044d2` ont terminé `success` : [suite ERP](https://github.com/Verwolfy/erp-mortier/actions/runs/42079472137), [audit](https://github.com/Verwolfy/erp-mortier/actions/runs/42079472496).
- URL Streamlit renseignée dans la documentation antérieure : `https://nextgent-erp.streamlit.app/`. Une capture d'utilisateur d'octobre atteste une session ADMIN passée, mais **aucune session authentifiée n'est disponible dans cette intervention**, et l'ouverture anonyme actuelle n'a pas abouti à une validation de l'interface. Ne pas déclarer le déploiement du dernier commit ni la validation visuelle des 9 onglets.
- Audit du job `.github/workflows/relances_quotidiennes.yml` : **relances planifiées les lundis et jeudis à 08:00 UTC** ; le job peut envoyer des courriels en production lorsque `ERP_ENABLE_EMAIL_SEND=true` et les variables de sécurité sont satisfaites. Jusqu'ici, il pouvait sélectionner des factures `DEMO26_*` au statut `VALIDE` et échues. Le fait que les adresses démo utilisent `.invalid` ne constitue pas un contrôle de sécurité suffisant.
- Correctif `scripts/envoyer_relances.py` : **exclut en tout mode les factures dont `facture_id` commence par `DEMO26_` ou dont `client_id` commence par `DEMO26_`**, avant le comptage des relances et tout appel SMTP. Aucun changement de données/SQL, pas de nouvelle activation d'email ; le traitement des autres factures conserve sa règle antérieure.
- Tests ajoutés dans `tests/test_relances_guard_010a.py` pour les scénarios de simulation du mode PRODUCTION : aucun envoi vers factures/clients DEMO26, et seule une facture non marquée peut déclencher l'envoi simulé. Les SMTP et données sont simulés, **aucun courriel réel envoyé**.
- Commits `0b9665ca` (correction) et `7299b6fd` (tests). Résultats CI des nouveaux commits encore à contrôler à la rédaction.
- **78 lignes fictives toujours en base** et **script SQL de rollback inchangé**. La correction du code source GitHub n'est pas une preuve que ce nouveau code est déjà déployé sur l'hôte Streamlit ou sur un autre exécuteur externe.
- Préalable à toute émission réelle : vérifier que l'automatisation GitHub exécute bien le commit corrigé. Si un autre exécuteur plus ancien est actif, suspendre ses relances jusqu'à sa mise à jour, sans désactiver arbitrairement les workflows sans preuve.

## Complément fictif de réconciliation des stocks — 2026-11-05

- Vérification de l'automatisation `.github/workflows/recalcul_stock.yml` : planification quotidienne à **02:00 UTC** ; le script `scripts/recalculer_stock.py` est un **audit en lecture seule**, ne corrige jamais les écarts. La présence d'écarts fictifs n'aurait pas modifié automatiquement les stocks, mais peut polluer les alertes du job.
- Contrôle SQL initial des quatre références `DEMO26_` : `MP1 100/100`, `MP2 220/0`, `SKU1 180/180`, `SKU2 60/0` (quantité stock / somme nette des mouvements). **Deux écarts fictifs confirmés**.
- Lot complémentaire `sql/demo/20261105_stock_opening_lot2_FICTIF.sql` : deux mouvements de stock d'ouverture `DEMO26_MV2` (MP2 : 220) et `DEMO26_MVP2` (SKU2 : 60), sans écriture de stock, sans données fiscales ni pièce réelle. Test transactionnel avec `ROLLBACK` réussi ; **insertion réelle** des deux seules lignes fictives exécutée.
- Contrôle SQL après insertion : **4/4 références fictives avec écart stock/mouvements = 0**. L'insertion ne garantit pas la réconciliation globale des stocks de production existants et n'affecte pas leurs lignes.
- Le jeu fictif comporte désormais **80 lignes en 53 tables**, réparties en lot 1 (78) et lot 2 (2).
- Deux possibilités de retour arrière, **non exécutées définitivement** :
  - `sql/demo/20261105_rollback_stock_opening_lot2_FICTIF.sql` suivi de `sql/demo/20261105_rollback_erp_kpi_FICTIF.sql` ;
  - **script unique recommandé** : `sql/demo/20261105_rollback_COMPLET_80_lignes_FICTIF.sql`, qui reprend les mêmes 55 `DELETE` dans une seule transaction, sans `CASCADE`.
- Vérification du rollback combiné **sur la base déjà chargée**, en remplaçant `COMMIT` par un `SELECT` et `ROLLBACK` : deux mouvements du lot 2, les deux factures et les deux clients fictifs deviennent temporairement absents (0), puis tous les changements d'essai sont annulés. **Ce script n'a PAS été exécuté avec `COMMIT`**.
- La version initiale du rapport plus haut indique 78 lignes : ce chiffre correspond seulement au lot 1. **Le total actuel est 80**.
- CI du correctif de relances du commit `f075bf62` : [tests ERP](https://github.com/Verwolfy/erp-mortier/actions/runs/42080065900) et [audit](https://github.com/Verwolfy/erp-mortier/actions/runs/42080066225) terminés **success**.
- L'accès public à `https://nextgent-erp.streamlit.app/` n'a pas permis de valider les écrans authentifiés ; tests UI Streamlit en session réelle restant à faire.

## Exécution par lots demandée — 5 novembre 2026

**Lot A — État et cohérence.** Les workflows du commit `74930d7d` ont terminé en `success` : [tests ERP](https://github.com/Verwolfy/erp-mortier/actions/runs/42080867511), [audit](https://github.com/Verwolfy/erp-mortier/actions/runs/42080867593). Vérification sur Supabase : les mouvements d'ouverture additionnels `DEMO26_MV2` et `DEMO26_MVP2` ainsi que les deux factures et les trois opportunités de démonstration sont toujours présents. **80 lignes fictives**, deux lots, rollback combiné non exécuté.

**Lot B — Sécurité des traitements planifiés.** Le script de relances exclut déjà les factures/clients `DEMO26_`; le job d'audit des stocks est **lecture seule**, sans correction automatique. Les exports SCF rejettent actuellement les pièces non validées ; la pièce de démonstration SCF est en `BROUILLON`. Attention : il reste nécessaire de s'assurer qu'aucune exportation officielle, notification ou relance hors de ces parcours ne reprend les données de démo. Aucun nouveau privilège ni aucune règle fiscale n'ont été créés.

**Lot C — Réversibilité du jeu 80 lignes.** Tests statiques renforcés dans `tests/test_demo_rollback_contract.py` pour exiger l'égalité exacte entre les 55 suppressions du rollback combiné et la concaténation des deux scripts individuels, l'ordre des opérations, une transaction unique et les deux lignes de mouvements d'ouverture. Un premier commit `68e42510` a échoué en CI pour deux erreurs des **expressions régulières des tests**, pas une erreur des données : inclusion accidentelle du mot CASCADE provenant d'un commentaire et motif INSERT exigeant un espace facultatif. Correctifs commits `82bb3af9`, `c42e3164`. Vérifier le verdict des deux workflows sur `c42e3164` avant de considérer ces nouveaux tests validés.

**Lot D — Validation applicative.** URL identifiée dans les notes de déploiement : `https://nextgent-erp.streamlit.app/`. Les 9 fonctions KPI et la barrière d'accès Streamlit ont des tests automatisés ; **aucune validation visuelle connectée** n'est attestée dans ce lot. Sans session navigateur autorisée, ne pas confondre tests unitaires/CI avec déploiement réel ou rendu fonctionnel.

**Décision de continuité :** travailler par lots complets avec bilan regroupé. Conserver le jeu actuel et le script de retour arrière intégral `sql/demo/20261105_rollback_COMPLET_80_lignes_FICTIF.sql`. Éviter tout ajout à la base pour combler artificiellement les tables techniques, fiscales ou de sécurité. Reprendre par vérification CI de `c42e3164`, puis inspection des anomalies de rendu/deployment à partir d'une session ERP effectivement accessible.

## Lots regroupés — CI, exports, contrôle SQL (suite du 5 novembre 2026)

### Lot 1 — Validation de référence
- Commit `180715bc` : deux workflows GitHub terminés en `success`, [tests ERP](https://github.com/Verwolfy/erp-mortier/actions/runs/42081667803) et [audit de réconciliation](https://github.com/Verwolfy/erp-mortier/actions/runs/42081667799). Les expressions régulières des contrôles du rollback 80 lignes ont été corrigées avant ce verdict.
- Les contrôles des 9 KPI et la simulation de la barrière RBAC Streamlit restent couverts par la suite automatisée ; cela **n'atteste pas** un parcours navigateur authentifié.

### Lot 2 — Protection des sorties fictives
- Audit : le job de relances `scripts/envoyer_relances.py` ignore `DEMO26_` avant courriel et comptage ; le job de stock `scripts/recalculer_stock.py` est sans écriture.
- Risque complémentaire confirmé dans le code : `core/export_scf.py` vérifiait `VALIDEE` mais pas l'origine fictive. **Correction appliquée sur `main`** (commit `d9dd30bf`) : refus d'export CSV pour une référence ou un journal commençant par `DEMO26_`, ou un compte SCF réservé `41199926` / `70199926` dans les lignes. Ceci bloque une pièce fictive même si son statut devient `VALIDEE`, sans empêcher l'export de pièces ordinaires valides.
- Tests locaux sans accès à la production ajoutés dans `tests/test_export_scf.py` (commit `0b5d21eb`) : 5 cas fictifs refusés et 1 cas valide conservé. **Vérifier le verdict CI du nouveau commit avant de déclarer ces tests exécutés avec succès.**
- La pièce SCF de démo en base reste en `BROUILLON` ; aucune écriture comptable ou validation juridique n'a été engagée.

### Lot 3 — Données et réversibilité
- `sql/demo/20261105_verification_erp_kpi_FICTIF.sql` étendu au lot 2 (commit `6126aff3`) : validation des deux mouvements d'ouverture et rapprochement de leurs quantités avec les stocks correspondants.
- **Exécution SQL réelle en lecture seule : `CONTROLES_DEMO_OK`.**
- Les **80 lignes fictives**, en 53 tables, sont conservées. Le rollback global `sql/demo/20261105_rollback_COMPLET_80_lignes_FICTIF.sql` reste **non exécuté définitivement** et disponible.
- Aucun changement de permissions, d'utilisateur, de schéma, de référentiel fiscal ou de données réelles lors de ce cycle.

### Lot 4 — Validation UI et suite
- URL documentée : `https://nextgent-erp.streamlit.app/`. Tentative d'ouverture publique par le navigateur externe non concluante ; **aucune authentification ni validation visuelle des neuf onglets n'a été réalisée**.
- Prochain cycle : confirmer les deux workflows GitHub de `6126aff3` et des éventuels commits documentaires, examiner les erreurs réelles s'il en existe ; vérifier le déploiement depuis la console de l'hébergeur quand elle est autorisée ; tester les neuf onglets avec le rôle `ADMIN` sans créer de nouveaux accès.
- Conserver les deux lots distincts pour traçabilité. Aucun rollback COMMIT avant la fin des essais.

## Cycle autonome en lots — validation du 5 novembre 2026

### Lot 1 — CI de référence
- La suite ERP complète du commit `090e9d28` a terminé en **success** : [tests](https://github.com/Verwolfy/erp-mortier/actions/runs/42083120637) et [audit sans modification](https://github.com/Verwolfy/erp-mortier/actions/runs/42083120566).
- Ce verdict inclut la correction de refus d'export SCF des pièces ou comptes fictifs. Le parcours Streamlit connecté reste une limite indépendante.

### Lot 2 — Contrôle exhaustif des lignes fictives
- Nouveau SQL lecture seule `sql/demo/20261105_verification_EXACTE_80_lignes_FICTIF.sql`, dérivé des **55 prédicats exacts** de `sql/demo/20261105_rollback_COMPLET_80_lignes_FICTIF.sql` (commit `e1f14b98`).
- Exécution sur Supabase principale : `CONTROLE_80_LIGNES_OK`, **55 prédicats**, **53 tables**, **80 attendues**, **80 observées**, **0 anomalie**. Il s'agit d'un comptage précis, pas d'une mutation.
- Test de cohérence versionnée `test_exact_80_line_verification_matches_every_rollback_predicate` ajouté dans `tests/test_demo_rollback_contract.py` (commit `631c744c`) : le contrôle SQL doit rester aligné sur le rollback, et aucune opération d'écriture n'est autorisée dans le SQL de contrôle.

### Lot 3 — Sécurité / réversibilité
- Protection déjà en code : relances `DEMO26_` ignorées avant SMTP ; exports SCF fictifs refusés ; audit des stocks lecture seule.
- Les **80 lignes démo** sont toujours en production Supabase ; **aucun retour arrière définitif exécuté**, aucun nouvel utilisateur, aucune correction fiscale ni modification des autorisations.
- Rollback principal complet : `sql/demo/20261105_rollback_COMPLET_80_lignes_FICTIF.sql`. Un essai transactionnel avec `ROLLBACK` avait été validé précédemment. Ce test ne garantit pas le succès futur si des dépendances utilisateur sont ajoutées entre-temps.

### Lot 4 — Continuité
- Vérifier les deux GitHub Actions du dernier commit, résoudre tout échec confirmé avant de poursuivre les lots de code.
- Le navigateur Streamlit authentifié `https://nextgent-erp.streamlit.app/` n'a pas été testé dans cette session ; aucune conclusion de déploiement ou d'affichage des neuf onglets ne peut être tirée de la seule CI.
- Le jeu de données fictives ne doit servir ni aux relances réelles, ni aux exports officiels, ni aux déclarations. Les montants des KPI simulés ne doivent pas être interprétés comme des montants comptables de l'entreprise.

## Cycle intégré additionnel SIM26 — achats → production → qualité → ventes → encaissement

**Décision utilisateur du 5 novembre 2026 :** alimenter rapidement les tables métier avec un scénario fictif réellement lié de bout en bout, exécuter en lots et poursuivre sans demander des approbations pour les tâches non critiques.

### État réellement appliqué sur Supabase principale
- **40 nouvelles lignes `SIM26_*` réparties sur 37 tables**, insérées avec `COMMIT` après prévalidation SQL transactionnelle avec `ROLLBACK`. Les **80 lignes `DEMO26_*`** existantes sont restées inchangées. Total **120 enregistrements fictifs** identifiés par les scripts, répartis sur les **53 tables métier** déjà couvertes par le jeu initial ; pas de remplissage de `auth`, `storage`, ni des référentiels de sécurité ou de réglementation.
- Cycle factuel relié : fournisseur et client fictifs ; 100 kg de matière première achetés et réceptionnés à 10 DZD/kg ; recette `SIM26_REC` 10 kg/unité ; OF `SIM26_OF` 10 unités ; qualité `SIM26_QC` conforme `OUI` ; SKU produit et lot ; devis et commande ; BL de 10 unités ; facture `SIM26_INV` 2 000 HT et 2 380 TTC **strictement illustratifs** ; règlement `SIM26_PAY` 2 380 ; lettrage `SIM26_MATCH` 2 380 ; facture fournisseur en brouillon, CRM, projet, tâche, feuille de temps.
- Flux MP +100/-100 = **0**, flux PF +10/-10 = **0** ; les nouveaux stocks MP/PF sont à 0 après le cycle, aucun stock des scénarios existants changé.
- **Deux vérifications de lecture seule après insertion et après essai de rollback :** `CONTROLE_80_LIGNES_OK` (55 contrôles, 53 tables, 80/80, 0 anomalie), et `SIM26` (40/40, 37 tables, 0 erreur d'identifiant, quantités cohérentes, qualité OUI et règlement/lettrage 2 380).
- **Rollback combiné de 120 lignes** `sql/demo/20261105_rollback_TOTAL_120_lignes_FICTIVES.sql` : **95 commandes DELETE** en transaction unique, avec retrait SIM26 avant DEMO26 (la feuille de temps SIM26 référence l'employé DEMO26). Exécuté à blanc en remplaçant le COMMIT final par un SELECT + ROLLBACK. Suppressions temporaires vérifiées ; le rollback **définitif n'a pas été exécuté**.

### Sources et commandes opérationnelles
- [Scénario complet](https://github.com/Verwolfy/erp-mortier/blob/main/docs/SCENARIO_SIM26_CYCLE_ACHAT_PRODUCTION_VENTE_20261105.md).
- Insertions : `sql/demo/20261105_seed_cycle_complet_SIM26_FICTIF.sql` (**déjà exécuté** ; ne pas rejouer sans retrait préalable).
- Vérification lecture seule : `sql/demo/20261105_verification_cycle_complet_SIM26_FICTIF.sql` ; ancien lot `sql/demo/20261105_verification_EXACTE_80_lignes_FICTIF.sql`.
- Rollback autonome `sql/demo/20261105_rollback_cycle_complet_SIM26_FICTIF.sql` ; rollback global `sql/demo/20261105_rollback_TOTAL_120_lignes_FICTIVES.sql` (**non exécutés définitivement**).
- Les documents historiques de démonstration portent des dates du **13 au 25 octobre 2026** ; sélectionner le mois d'**octobre 2026** pour les retrouver dans les listes filtrées par période. Les chiffres réglementaires sont exclusivement des valeurs de simulation, **non des taux fiscaux vérifiés à date**.

### Sécurité, CI et prochaines actions
- Ajout du préfixe `SIM26_` à l'exclusion des **relances SMTP** (script `scripts/envoyer_relances.py`) et des **exports SCF** (`core/export_scf.py`). Les cas correspondants ont des tests de régression locaux sans connexion SMTP, DB ou validation fiscale.
- Tests automatisés de correspondance exactes du seed SIM26 (40 INSERT), rollback SIM26 (40 DELETE), et rollback global (95 DELETE), plus lectures de vérification ; inspecter et réparer les éventuels échecs CI.
- Ne jamais déduire de la seule CI que l'interface Streamlit sur `https://nextgent-erp.streamlit.app/` a été redéployée ou que ses transitions transactionnelles ont été exécutées : **les lignes ont été insérées par SQL pour simuler le résultat**, pas par les boutons des écrans. L'utilisateur veut pouvoir les visualiser et tester les parcours.
- **Próchaine action :** vérifier les deux workflows du commit le plus récent, corriger tout test échoué, ensuite faire le contrôle visuel authentifié si une session est disponible. Ne pas ajouter des utilisateurs réels, des permissions, des règles fiscales ou des messages externes pour étendre la démonstration.
