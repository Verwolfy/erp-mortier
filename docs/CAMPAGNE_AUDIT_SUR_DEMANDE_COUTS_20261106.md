# Lot 046 — Audit analytique sur demande
Date : 2026-11-06

## Résultat vérifié
- GitHub : `Verwolfy/erp-mortier`, branche `main`.
- Commit validé `5ac3ce7c2660127ce321f62e6d60d5961a623159`.
- [Suite ERP](https://github.com/Verwolfy/erp-mortier/actions/runs/42215999054) : SUCCESS, **2615 passed, 7 skipped, 133 warnings**.
- [Audit de réconciliation](https://github.com/Verwolfy/erp-mortier/actions/runs/42215998971) : SUCCESS.
- Aucun changement SQL ni données comptables ou de stock. Le projet Supabase TEST n'a pas été réveillé pour ce lot.

## Constat
Dans le lot 045, `get_period_report(period_id, sections=(section,))` ne lisait que la section sélectionnée mais exécutait encore `erp_cost_period_audit` à chaque navigation. L'audit SQL comprend plusieurs agrégations et calculs d'allocations ; cela peut coûter cher sur de grosses périodes, sans besoin d'exposer un audit sur chaque simple consultation.

## Modifications appliquées
- `modules/production/cost_service.py` : signature `get_period_report(period_id, *, sections=None, include_audit: bool = True)`. Le défaut `True` conserve la compatibilité des autres appelants ; `False` évite complètement la RPC d'audit. Le résultat contient `audit=None` et `audit_calculated=False` lorsqu'il n'est pas calculé. Refus des valeurs non booléennes. Pas de cache, pas d'audit périmé.
- `modules/production/cost_views.py` : case à cocher « Calculer l'audit complet de la période » (désactivée par défaut). Sans calcul demandé, l'interface ne présente pas un audit fictivement conforme ; elle affiche explicitement « Audit non calculé ». Si demandé, elle exécute et affiche le véritable audit. L'échec de chargement reste bloquant pour les formulaires d'écriture.
- `tests/test_industrial_cost_views_flows.py` : tests de non-recalcul par défaut, recalcul explicite et échec bloquant.
- `tests/test_industrial_cost_pagination.py` : tests d'absence de RPC quand audit désactivé, comportement historique audit activé, refus d'un paramètre invalide et absence de mise en cache pour deux audits successifs.

## Invariants de sécurité maintenus
- Les contrôles des droits Production + Finance restent obligatoires.
- La RPC PostgreSQL `erp_cost_validate_period` recalcule elle-même l'audit obligatoire avant le passage `VALIDE` ; l'interface ne peut pas contourner le garde SQL en décochant la case.
- Aucune écriture de données, aucun montant SCF, aucun mouvement stock et aucun effet CUMP dans ce lot.
- La pagination peut toujours refuser un résultat partiel ou désordonné.
- Le mode `include_audit=True` reste l'option par défaut des éventuels appelants historiques du service.

## Limites
- Une estimation chiffrée du gain de latence sous charge réelle n'a pas été effectuée ; les tests prouvent surtout l'absence d'appel RPC d'audit lorsqu'il est désactivé.
- La pagination HTTP ne représente pas une transaction instantanée de certification.
- Le test navigateur authentifié avec vrais profils n'est pas encore effectué.
- 7 tests ignorés et 133 avertissements restent à classifier dans une campagne technique distincte.

## Suite recommandée
1. Qualification dans le navigateur de l'interface avec profil Production + Finance et profil limité.
2. Profilage de `erp_cost_period_audit` sur un environnement de TEST avec jeux volumétriques fictifs transactionnels et `EXPLAIN`, sans modification de la production.
3. En cas de besoin d'exports officiels, implémenter un instantané cohérent transactionnel avant tout statut « certifié ».
