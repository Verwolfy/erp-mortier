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
