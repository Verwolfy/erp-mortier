# LOT-13 — Sécurité & Utilisateurs : affichage exclusif

**Date :** 8 novembre 2026. **Statut :** changement de code uniquement, sans mutation de données.

## Constat

La fonction `show_user_management` utilisait `st.tabs` et exécutait les quatre sections : création d'utilisateur, définition de permission, annuaire et piste d'audit. Même en remplissant un formulaire sans le soumettre, la page lisait `get_users`, `get_permissions` et `get_audit_logs`. Cela alourdissait le rendu et augmentait l'exposition inutile de données sensibles.

## Changement

- `Vue Sécurité` utilise `st.selectbox` après le contrôle `is_security_manager()`.
- Un seul panneau est exécuté. Les listes d'utilisateurs et de permissions sont chargées **uniquement** sur `Annuaire Existant` ; les journaux le sont **uniquement** sur `Piste d'Audit (Logs)`.
- Les formulaires utilisateurs et permissions restent inchangés ; les opérations sensibles continuent de revalider leurs droits dans les services et RPC existantes.
- Les hachages `hash_mdp` restent exclus de l'affichage de l'annuaire.
- Le callback de sélection marque une interaction sans renouveler la session directement.

## Acceptation

`tests/test_lot13_security_lazy.py` teste les quatre panneaux, la non-lecture des données sensibles hors écran, le refus du rôle, la confidentialité des hash et le callback d'activité. CI complète puis vérification du SHA fusionné sur `main`.

**Aucune migration, aucune modification de compte, de rôle, de mot de passe, de RLS ou de données Supabase.**

## Suite

LOT-14 Administration Référentiels : remplacer les dix onglets principaux par une navigation exclusive, en bornant aussi les appels aux listes de choix au formulaire actif. Ne pas modifier `DB-UNI-01` gelé ni les valeurs réglementaires. Tests E2E authentifiés et environnement Supabase TEST isolé toujours requis.