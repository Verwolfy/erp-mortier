# LOT-08 — Chargement à la demande des 5 vues Production

Date : 2026-11-08. Branche : `perf/lot08-production-lazy-20261108`.

## Diagnostic

Dans `show_production_page`, les cinq onglets Streamlit (Recettes, OF, Production/CQ, Historiques et Coûts) sont calculés à chaque rendu, ainsi que les catalogues de produits finis, MP et SKU pour tout utilisateur habilité à écrire. L'ouverture des Coûts ou de l'Historique entraînait donc des lectures et calculs de fabrication non sollicités.

## Correction

- Un sélecteur **Vue Production** exécute uniquement la vue choisie, **après vérification des droits à partir du compte actif en base**.
- Recettes : lit les produits et matières premières, pas les SKU inutiles.
- OF / Suivi Production & CQ : lit les trois référentiels requis.
- Historiques : aucun référentiel de création ; la pagination n'est déclenchée qu'au clic utilisateur.
- Coûts industriels : n'appelle que `show_cost_reference`, qui conserve ses contrôles Production et Finance.
- En lecture seule : aucun catalogue de création n'est chargé ; les écrans métiers conservent leurs garde-fous.
- Aucun changement au service de fabrication, aux quantités, conversions, opérations, contrôles qualité, clôtures, droits, SQL ni données.

## Acceptation

- 8 tests supplémentaires vérifient l'absence des calculs non sélectionnés, l'absence de lecture catalogue en mode historique ou coûts, RBAC avant sélection, lecture seule et callback d'activité.
- Adaptation du contrat historique de nombre de `selectbox` ; affichage Coûts en lecture seule désormais sélectionné explicitement dans le test.
- Exécuter les deux workflows GitHub complets sur cette PR et sur `main` après fusion.
- Un gain d'appels Python est attendu ; le gain réel de latence doit être mesuré via OPT-04 une fois la version déployée confirmée.

## Limites et suites

- Le site Streamlit connecté et la base Supabase TEST n'ont pas été validés ici ; ne pas prétendre le contraire.
- La recette E2E en environnement TEST isolé est toujours nécessaire pour les transactions de fabrication.
- Rotation du mot de passe administrateur toujours prioritaire.
- Pas de changement de coûts SQL, index ni fiscalité sans mesure probante et paramètre juridique validé.
