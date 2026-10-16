# Checklist de tests PostgreSQL à faire AVANT toute mise en production

Ces cas ne sont **pas** considérés comme exécutés ici.

1. En rôle `anon`, les RPC retournent une erreur de permission.
2. Un rôle `authenticated` sans présence dans `erp_hardening.company_members` ne peut ni recevoir ni fabriquer.
3. Un membre de la société A ne peut agir sur la société B.
4. Une réception correcte crée un lot, un mouvement `IN`, une opération unique, un résultat idempotent.
5. Une réémission de même `operation_id` et de mêmes paramètres retourne le même résultat sans dupliquer les mouvements.
6. Une réémission de même UUID avec valeurs différentes échoue sans écriture.
7. Deux réceptions simultanées portant le même code lot : une seule valide, l'autre échoue sans mouvement.
8. FIFO de lots 10 kg coût 2 puis 20 kg coût 3 : OF de 15 kg consomme 10 puis 5, coût MP total 35.
9. OF demandant plus que disponible : aucune modification des stocks, aucun lot PF, aucune opération partielle.
10. Deux OF simultanés ne peuvent pas consommer deux fois le même reliquat.
11. Deux recettes multi-composants aux ordres d'articles différents ne bloquent pas mutuellement de façon permanente (deadlock).
12. La modification d'une recette `APPROVED` est refusée; la création/mise à jour/suppression de ses lignes est également refusée.
13. Une recette vide ne peut pas être approuvée, une recette archivée ne peut pas produire.
14. Les déclencheurs et clés étrangères rejettent les lignes qui mélangent des sociétés ou des lots d'articles différents.
15. Les quotas et performances de Supabase restent acceptables pour 100, 1000, 10000 lots ; les index sont réellement utilisés (`EXPLAIN ANALYZE`).
16. Les comptes de service et les politiques RLS existants ne permettent aucun accès non prévu.
17. Comparer calcul BOM Python / PostgreSQL pour les mêmes quantités aux limites de précision.
