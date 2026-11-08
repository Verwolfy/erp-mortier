# LOT-14 — Administration Référentiels : exécution exclusive des 10 vues

**Date :** 8 novembre 2026. **Statut :** optimisation de l'interface, sans modification des données.

## Problème traité

`show_admin_page` lançait les dix onglets `st.tabs` même lorsque l'utilisateur n'en consultait qu'un. En plus des sections Clients, Fournisseurs, Matières premières, Produits, SKU, Listes, Exonérations, Qualification fiscale, Documents et Qualité, les cases de formulaire restées ouvertes dans `st.session_state` pouvaient déclencher des lectures `get_opts` de référentiels non visibles.

## Changement

- `Vue Administration` présente dix choix ; une seule vue est exécutée.
- Chaque case `ng_admin_create_*` ou `ng_admin_full_*` n'autorise un chargement de liste de choix que lorsque **sa vue correspondante est sélectionnée**. L'écran Qualité, Documents, Fiscalité ou Exonérations ne déclenche plus les lectures de catégories d'un ancien formulaire masqué.
- Les moteurs de création, les contrôles d'unicité tiers (NIF/RC), l'édition des champs sensibles, le droit serveur d'écriture, les exports et les audits sont conservés.
- Le droit historique `Administration.ecriture` détermine toujours l'accès aux formulaires ; aucun privilège n'est ajouté ni mise à jour de sécurité effectuée.
- Les documents NextGen conservent leur mode brouillon ; aucun agrément réglementaire n'est déduit de cette optimisation.

## Tests

- `tests/test_lot14_admin_lazy.py` : 10 vues indépendantes, aucune lecture de catalogues hors écran, flag d'autre vue ignoré, formulaire Client lit ses seuls catalogues, lecture seule, callback d'activité et contrat AST.
- `tests/test_admin_conditional_form_reads.py` : les anciens contrats AST sur les blocs `tab5` et `tab_listes` sont mis à jour pour vérifier les nouveaux blocs conditionnels, en conservant les protections de chargement explicite.
- CI complète en PR avant toute fusion, puis CI sur le commit `main` fusionné.

## Bénéfices et limites

La mesure prouvée porte sur la non-exécution des vues et des appels `get_opts` non consultés, **pas** sur une baisse mesurée en millisecondes.

La page Administration complète utilise encore le rôle en session pour déterminer le mode d'écriture affiché ; les services sensibles effectuent leurs propres contrôles serveur. Un audit de durcissement de la lecture et de l'identité d'Administration est une tâche de sécurité distincte, non comprise dans cette PR.

Aucune migration PostgreSQL, modification Supabase, changement de permissions, insertion de tiers, import juridique/fiscal, rotation de mot de passe ou changement de numérotation. `DB-UNI-01` demeure gelé.

## Suite

Valider l'ensemble des vues Administration sur Streamlit Cloud authentifié, notamment les référentiels Client/Fournisseur, le document NextGen et les dossiers fiscaux. Poursuivre les révisions de sécurité du rôle affiché, la mesure OPT-04 et la préparation de l'environnement TEST avant les migrations.