# Cotisations sociales — référentiel documentaire Algérie 2026

**Pourquoi.** Le décret exécutif n° 15-236 du 3 septembre 2015, publié au
Journal officiel algérien n° 49 du 16 septembre 2015, page 7, répartit la
cotisation générale ainsi :

| Part | Taux du décret | Code de référence SQL |
|---|---:|---|
| Employeur | 25 % | CNAS_REG_GENERAL_EMPLOYEUR_REF |
| Salarié | 9 % | CNAS_REG_GENERAL_SALARIE_REF |
| Fonds des œuvres sociales | 0,50 % | CNAS_REG_GENERAL_FONDS_OEUVRES_REF |
| Total | 34,50 % | Somme de contrôle (non insérée comme taxe supplémentaire) |

**Source primaire :**
https://www.joradp.dz/FTP/jo-francais/2015/F2015049.pdf

Le CLEISS, sur sa fiche de cotisations publiée pour 2024, présente la
même répartition et distingue notamment le financement du fonds :
https://www.cleiss.fr/docs/cotisations/algerie.html

**Comment.** La migration 024 enregistre trois paramètres uniquement
documentaires dans le registre réglementaire : suffixe `_REF`,
`statut_juridique=a_confirmer`, `niveau_confiance=RECOUPEE`,
unité `fraction`, période de référence limitée à 2026. La date
`2026-01-01` est le début de l'instantané documentaire, **pas**
la date d'entrée en vigueur historique du décret de 2015.

**Pourquoi ne pas activer.** L'application ne dispose pas encore de
la qualification du régime et du secteur des salariés, des éléments
soumis aux cotisations, des éventuels dispositifs de réduction ou
cotisations complémentaires, ni d'une vérification exhaustive des
changements postérieurs au décret. Certaines sources commerciales
mentionnent 26 % employeur sans distinguer les contributions annexes.
La source primaire distingue expressément 25 %, 9 % et 0,50 %.

Les codes de paie `CNAS_SALARIE_TAUX` et
`CNAS_EMPLOYEUR_TAUX` **ne sont pas créés** : aucun calcul
de paie n'utilise automatiquement les nouvelles valeurs.

La migration ne modifie ni bulletin, salarié, facture, journal,
RLS, accès public ni plan comptable. L'étape de mise en service
nécessite des règles par catégorie et une validation complète
des assiettes et des contributions distinctes.


## Déploiement vérifié — 29 octobre 2026

Migration Supabase `erp_024_cnas_references_documentaires_20261029`
appliquée avec succès sur TEST puis PRODUCTION.

Contrôles SQL identiques dans les deux environnements :
**3 références**, total `0.345` (34,5 %), **0 paramètre de
paie exécutable** `CNAS_SALARIE_TAUX` ou `CNAS_EMPLOYEUR_TAUX`,
**0 employé**, RLS active et aucune lecture `anon`.
Aucun bulletin ni règlement n'a été modifié ou créé par ce lot.

Le statut `a_confirmer` est volontaire : les références du décret 2015
sont conservées pour revue du régime général et des éventuelles dispositions
sectorielles/amendements, non pour calculer les retenues.
