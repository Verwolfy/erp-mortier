# Prévention des doublons Clients/Fournisseurs — Sofiane ERP

**Diagnostic vérifié le 7 novembre 2026.**

## Situation initiale
- `clients` : 10 lignes ; `fournisseurs` : 9 lignes.
- Aucun doublon **exact après mise en minuscules et suppression des espaces en bordure** dans les noms, NIF ou RC renseignés à cette date. Cette vérification ne prouve pas l'absence de doublons orthographiques.
- Schéma Supabase : uniquement PK uniques `client_id` et `fournisseur_id`. Aucune contrainte UNIQUE sur `nom`, `nif` ou `rc`.
- Avant correction, `add_client()` et `add_fournisseur()` lisaient les références pour générer `CLI-*` ou `FRN-*`, sans vérifier les identités métier.

## Correctif livré dans la PR
- `modules/admin/tier_dedup.py` : comparaison conservatrice des noms avec accent/casse/espacement neutralisés, NIF et RC non vides comparés sans séparateurs.
- `modules/admin/service.py` : lecture **paginée stricte** du référentiel complet avant création ; refus explicite des doublons et d'une lecture refusée, partielle ou indisponible. Pas de création si doute. Fiche entrante non modifiée ; insertion et dual-write inchangés.
- `modules/admin/views.py` : avertissement spécifique et ID de la fiche existante, sans afficher le NIF/RC ; aide dans les deux formulaires.
- `tests/test_admin_tier_duplicates.py` : doublons et lectures incomplètes refusés ; aucun appel d'insertion ; normalisation et conservation des données originales.

## Limites à ne pas dissimuler
- **La vérification applicative n'est pas atomique :** deux soumissions concurrentes peuvent contourner le contrôle si elles se produisent entre lecture et insertion.
- **Une contrainte d'unicité partielle et normalisée en base, et éventuellement une RPC transactionnelle** sont nécessaires à une garantie absolue pour les nouveaux enregistrements. Le choix des clés métiers (NIF, RC, pays, exceptions multi-établissements) doit être validé avant toute migration de production.
- Aucun index UNIQUE sur le nom seul n'est recommandé sans revue : des sociétés juridiquement distinctes peuvent avoir une désignation semblable.
- Le contrôle s'applique ici à la **création** ; les modifications directes de noms/NIF/RC dans les tableaux doivent recevoir une revue équivalente ou être protégées par la future contrainte SQL.
- Une même société peut légitimement exister une fois comme cliente et une fois comme fournisseur.

## Préconisation
1. Conserver les références DEMO/SIM jusqu'à finalisation de l'ERP ; ne rien purger.
2. Valider la politique d'identité métier (NIF, RC, étendue géographique et cas particuliers).
3. Envisager une migration SQL non destructive avec index partiels pour les champs légaux normalisés, après audit de collisions, plan de déploiement et approbation de la modification de schéma.
4. Ne pas afficher « garanti par la base » tant que la contrainte n'existe pas.
