---
titre: Comptabilité SCF - Préparation des écritures
module: comptabilite
roles_autorises: [ADMIN, COMPTABLE, DIRECTION]
version: 1
date_maj: 2026-10-28
regles_liees: [SCF-001]
---
# Comptabilité SCF — état de développement

## Fonctionnement
Le socle vérifie le journal, la référence, la date, l'exercice ouvert, les comptes autorisés et l'équilibre débit/crédit de chaque pièce en dinars algériens.

Les pièces sont **préparées**, pas directement comptabilisées. La validation transactionnelle et la génération automatique d'écritures à partir de ventes/achats/paie restent à intégrer après tests SQL.

## Sécurité
Les pièces validées seront immuables après mise en place de la migration 014. Toute correction devra être réalisée par une nouvelle écriture de contrepassation.

## Contrôles
- Journal et période ouverte
- Comptes actifs et mouvementables
- Débit égal au crédit
- Écritures validées uniquement pour les balances
- Exports internes réservés aux rôles habilités

**Attention :** la conformité SCF complète et les états financiers réglementaires ne sont pas encore certifiés. Les exemples sont fictifs.

## Consultation de la balance SCF (prototype, nouvelle interface)

Dans **Finance → Balance SCF**, un utilisateur doit disposer du droit
`SCF / lecture`, vérifié à nouveau sur la base au moment de l'ouverture.
Il peut déclencher une lecture du journal validé, sans insertion ni mutation.

La lecture arrête tout affichage lorsque les données sont incomplètes,
qu'une pièce est déséquilibrée ou que le registre SCF n'est pas installé.
La balance ne contient **aucune donnée inventée** et n'est pas un état
financier officiel.

La consultation est limitée à 999 pièces et 9 999 lignes pour garantir
l'exhaustivité. Au-delà, une future procédure d'export serveur, protégée
et paginée, devra remplacer l'affichage.

**Prérequis :** migration 014 après autorisation RLS/GRANT et tests sur TEST.
Avant cela, l'onglet affiche une indisponibilité, jamais des chiffres fictifs.
