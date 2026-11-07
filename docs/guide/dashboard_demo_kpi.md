# Tableaux de bord ERP — mode démonstration isolé

**Version :** `DEMO-KPI-20261107-01` · **Périmètre :** 9 onglets KPI, lecture uniquement.

## Fonctionnement
- Dans **Tableaux de bord & KPIs**, activer **Mode démonstration — scénarios fictifs des 9 tableaux de bord**.
- Une bannière avertit que toutes les valeurs affichées sont fictives et entièrement calculées en mémoire par `modules/dashboards/demo.py`.
- Les 9 rubriques utilisent le **même** code de calcul que les données réelles, mais lisent uniquement le catalogue de démonstration dans `dashboard_read_scope(demo_rows=...)`.
- Le mode normal reste le comportement par défaut : il conserve les références existantes `DEMO` et `SIM` dans Supabase et affiche un avertissement de provenance tant qu'elles restent en base.
- Désactiver le bouton pour revenir aux tableaux réels, sans mélanger les deux sources.

## Couverture métier du scénario
| Domaine | Données fictives et tests des graphiques |
|---|---|
| Direction | Facturation du mois, trésorerie, créance échue, matière sous seuil et matière sans seuil |
| Rentabilité | Factures et lignes, coût PF actuel, règlement OPEX, net de paie simulé (non officiel), cascade waterfall |
| Ventes | Factures validées, facture en brouillon exclue, créance ancienne, classement des clients, série journalière |
| Achats | Commandes en retard/réceptionnées, prix matière en DZD et EUR fictifs avec taux fictif documenté, filtrage par unité |
| Stocks | Matières et PF, deux seuils d'alerte, une référence sans seuil, lot expiré, à échéance et sans date |
| Production | OF planifiés/en cours/terminés/rejetés, contrôles qualité conformes et non conformes, courbes cohérentes |
| CRM | Opportunités ouvertes, gagnées, perdues et leur probabilité |
| RH | Employés actifs/inactifs et congés en attente |
| Finance | Encaissements/décaissements validés, paiement en brouillon exclu, affectations partielles et solde indicatif |

## Séparation et sécurité
1. **Aucune écriture SQL, aucune migration ni création de données dans Supabase** : les scénarios supplémentaires sont des dictionnaires Python en mémoire.
2. Les références générées commencent toutes par `DEMO-KPI-` ou `SIM-KPI-`, sans noms de salariés réels ni pièces SCF.
3. Le contexte est isolé par `ContextVar`, réinitialisé en sortie et copié pour éviter les modifications mutuelles ; si une table de démonstration manque, **erreur immédiate**, jamais de repli vers le client Supabase.
4. Les contrôles RBAC des tableaux de bord restent actifs avant l'affichage des onglets ; le mode démo n'autorise pas l'accès à un module interdit.
5. Les montants, prix et taux de change fictifs sont **des valeurs de test**, pas des offres commerciales ni des règles fiscales ou légales.
6. Le mode démo ne permet aucun paiement, création d'OF, écriture de stock, validation SCF ou opération de RH ; seuls les graphiques utilisent les données.

## Fiabilisation des KPI
- Les scénarios couvrent les filtres de dates, la source des graphiques, la somme des valeurs quotidiennes, les statuts, les ratios conditionnés par leur dénominateur et les courbes vides.
- `tests/test_dashboard_demo_mode.py` : vérifie les 9 calculs en bloc, la séparation des contextes, le refus des lectures réelles et l'absence de fusion de données.
- `tests/test_dashboard_kpi_visuals.py` : couvre le P&L indicatif, les conversions d'achats, les risques lots, la provenance et les ratios N/D.
- Toute future mesure nécessitant des temps machines (TRS/OEE), des livraisons attendues/réelles (OTIF) ou un coût industriel réel validé reste **non calculable** à partir de ces seules valeurs.

## Avant suppression des références de développement
1. Inventorier les dépendances de toutes les références `DEMO/SIM` : lots, OF, stocks, factures, paiements, RH, CRM, achats.
2. Qualifier les lignes avec les responsables métiers et comptables ; **un préfixe seul n'autorise jamais une suppression**.
3. Tester un plan de nettoyage avec contraintes FK, traçabilité, sauvegarde, procédure de retour arrière et contrôle d'intégrité dans un environnement isolé.
4. Obtenir l'approbation explicite avant toute suppression de données ou modification des comptes en production.
5. Le jeu `DEMO-KPI-` en mémoire pourra être conservé dans les tests de non-régression même après suppression des données de développement en base.

**La réussite de GitHub Actions ne prouve pas l'affichage réel dans Streamlit hébergé : vérifier le repère `SOF-ERP-20261107-DEMO-01` en session authentifiée.**
