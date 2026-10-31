# Décision de réconciliation des migrations — 31 octobre 2026

## Vérifié en direct
- Projet Supabase PRODUCTION : `wenydirqtmkywbxbxfal`.
- Historique Supabase : **21 versions enregistrées, de 012 à 032 inclus**. Aucune version numérique manquante dans cette série.
- Le registre applicatif `public.schema_migrations` reste **vide (0 ligne)** : il ne prouve pas l'absence des migrations Supabase.
- Garde-fous SQL présents : fonction de précontrôle 031, fonction privée de facturation 032 et déclencheur 032 actif sur `public.factures`.
- La liste des fichiers `sql/` contient des brouillons et des scripts de vérification/rollback : ce ne sont **pas** des migrations toutes destinées à être exécutées.
- `sql/013_facturation_parametree.sql` se déclare explicitement BROUILLON, modifie le RPC de facturation et comprend REVOKE/GRANT. Il **n'est pas autorisé à être appliqué** sans revue des effets, validation des paramètres et des permissions.
- `sql/014_scf_journal.sql` et `sql/015_paie_privee.sql` se déclarent également BROUILLON ; les tables SCF et paie existent déjà, pas de rejeu aveugle.

## Décision
- **Zéro migration Supabase supplémentaire appliquée** : la série 012–032 est déjà enregistrée.
- **Pas de remplissage automatique** de `public.schema_migrations` : l'attribution d'une empreinte SHA-256 exige une correspondance probante entre les scripts et les opérations réellement effectuées ; le nom des versions ne suffit pas.
- **Aucun script de rollback, modification RLS/GRANT ou réécriture du RPC fiscal**.
- Des écarts de contenu et l'état précis de la facturation paramétrée demeurent à certifier. Ne pas présenter cet état comme une réconciliation exhaustive du schéma ni comme une homologation fiscale.

## Suite
1. Construire la matrice prouvée des 21 versions, empreintes des scripts concernés, objets SQL et validations de comportement.
2. Isoler les brouillons réglementaires et de permissions de l'historique déjà appliqué.
3. Après validation technique, régulariser le registre applicatif à partir d'empreintes démontrées, sans rejouer les DDL déjà en place.
