# Précontrôle réglementaire TVA daté — 8 novembre 2026

## Objectif et portée

Corriger le diagnostic réglementaire en **lecture seule** sans modifier la facturation opérationnelle ni prétendre à l'homologation fiscale. Aucun taux ni plafond juridique n'est ajouté, déduit ou modifié. Les valeurs sont exclusivement celles du registre `public.parametres_reglementaires`, contrôlées par `core.reglementation.chercher_parametre`.

## État avant correction

`core/preflight_reglementaire.py` comparait `TVA_TAUX_NORMAL` et `TVA_TAUX_REDUIT` aux nombres figés dans le code, ce qui empêchait l'évolution historique du registre. Il ne lisait ni `date_effet`, ni `date_fin`, ni `source`, ni `date_verification`.

## Correction versionnée

- Le précontrôle exige une **valeur unique applicable** à la `date_reference` (paramètre facultatif du diagnostic ; à défaut, date du jour **pour le diagnostic uniquement**).
- La sélection utilise `chercher_parametre` : statut `en_vigueur`, niveau `CONFIRMEE`, source non vide, dates ISO valides, période applicable, unité `fraction`.
- Un taux situé hors de `[0,1]` est rejeté. Absence, chevauchement, statut `a_confirmer` ou non-vérifié, source absente ou date invalide provoquent `PreflightIndisponible`. Les versions successives sans chevauchement sont prises en charge.
- Le précontrôle reste **non activateur** : `facturation_reglementaire_prete=False`, `comptabilisation_scf_prete=False`. La clé historique `reference_tva_officielle` reste un **signal interne de présence de deux valeurs confirmées dans le registre** et **ne certifie pas** indépendamment la validité du texte fiscal source.
- Les tests prennent des **valeurs fictives** et vérifient changement de taux sans changement de code, date d'effet, rétroactivité, absence de source, valeurs non confirmées et refus des chevauchements.
- Le scanner `scripts/auditer_parametres_reglementaires.py` reste non bloquant pour les six anomalies historiques déjà connues, mais `tests/test_auditer_parametres_reglementaires.py` interdit désormais toute **nouvelle** occurrence détectée, sans traiter le passif comme conforme.

## Inventaire réglementaire réel (lecture seule)

Contrôle SQL du projet `wenydirqtmkywbxbxfal` :
- 2 codes TVA (`TVA_TAUX_NORMAL`, `TVA_TAUX_REDUIT`) en `en_vigueur` / `CONFIRMEE`, avec dates de vérification ; l'existence en base **ne remplace pas une revue de la source juridique primaire**.
- 3 codes CNAS (`CNAS_REG_GENERAL_*`) toujours `a_confirmer` / `RECOUPEE` ; aucune activation automatique autorisée.
- Le RPC de production `public.erp_sale_transaction` comprend encore des constantes TVA/timbre et **ne consulte pas** `parametres_reglementaires`.
- Trois constantes Python historiques `TAUX_TVA`, `TAUX_TIMBRE`, `MAX_TIMBRE` subsistent dans `modules/ventes/service.py`. Trois autres occurrences sont présentes dans `sql/005_atomic_sales.sql`.
- Aucun nouveau paramètre de timbre confirmé n'a été chargé. Il serait dangereux de modifier silencieusement les montants facturés ou de remplacer le RPC avant un essai intégral.

## Vérification et suite

Les tests unitaires et la suite complète GitHub sont la preuve de validité **logicielle** de ce lot uniquement ; noter les IDs des workflows lorsque terminés. Ne pas affirmer de test SQL d'intégration.

La refonte de l'émission des factures **reste bloquée** par : environnement Supabase TEST inactif, paramètres timbre et cas d'exonération à certifier, parité Python/RPC à démontrer sur scénarios datés, revue des droits et des migrations, validation par expert-comptable algérien.

**Données/production** : aucune écriture Supabase, aucun changement de taux fiscal ou de droits, aucune suppression de données DEMO/SIM. Dépôt GitHub : `main` uniquement.
