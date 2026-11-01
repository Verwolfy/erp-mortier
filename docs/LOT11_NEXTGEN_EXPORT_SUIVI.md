# Lot 11 — Export du registre de qualification NextGen (lecture seule)

Date : 2026-11-01 — **aucune autorisation de commercialisation**.

## Objectif
Depuis Administration > Qualification TVA SKU > Préparation NextGen, fournir au `SECURITY_MANAGER` un export CSV utilisable pour rassembler **hors de l'ERP** les pièces techniques, fiscales et commerciales qui manquent encore. Le bouton est absent pour les comptes non habilités.

## Implémentation
- Le service `lister_blocages_nextgen()` conserve l'accès SQL **SELECT uniquement**, le contrôle du rôle, les limites de lecture et les statuts facturation/fabrication à `False`.
- `exporter_registre_nextgen_csv(result)` revalide le rôle `SECURITY_MANAGER` et refuse tout résultat tronqué, invalide ou marqué comme autorisé.
- CSV UTF-8 avec BOM et séparateur point-virgule : `sku_id`, `pf_id`, `format`, `unite_vente`, `blocages`, `reference_preuve_a_completer` (vide), `statut_qualification` (toujours `NON_VERIFIE`).
- Protection des valeurs importées contre l'interprétation comme formule dans un tableur (`=`, `+`, `-`, `@` en tête de champ).
- Aucun nom/contact, prix, valeur fiscale, donnée de demande web ou secret n'est exporté. Aucune modification Supabase, aucune synchronisation du fichier vers le site, aucun e-mail et aucune écriture de preuve dans l'ERP.
- **Ne pas versionner les CSV générés depuis Supabase dans le dépôt public.** Le fichier local exporté reste un document de travail interne à sécuriser.

## Limites et validations
- L'export ne garantit pas qu'une preuve jointe a été vérifiée : aucune qualification ne passe automatiquement à « validée ».
- Toute décision commerciale ou fiscale nécessite la pièce source et l'approbation appropriée.
- Le produit `PROOF-PU-SEAL` sans SKU reste signalé dans le panneau et n'est pas créé artificiellement par l'export.
- Revue juridique et expert-comptable algérien requises selon le type d'information avant usage fiscal/commercial.

## Tests prévus
- Tests de l'en-tête et des colonnes autorisées, refus d'une donnée supplémentaire, d'un rôle non autorisé, d'un snapshot mal formé et du contournement des drapeaux.
- Échappement de formule ; le bouton UI doit rester après contrôle `is_security_manager()` et en l'absence de méthodes de mutation.
- `pytest -q tests/test_nextgen_readiness.py` puis suite intégrale via CI GitHub.

**Statut de lot : vérifications CI requises avant fusion sur `main`.**
