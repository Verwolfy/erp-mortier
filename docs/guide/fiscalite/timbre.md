---
titre: Droit de timbre de quittance - reglements
module: fiscalite
roles_autorises: [ADMIN, COMPTABLE]
version: 1
date_maj: 2026-10-28
regles_liees: [TIMBRE-QUITTANCE-001]
---
# Timbre de quittance : séparation des règlements et de la facturation

## Source officielle retrouvée

**Journal officiel algérien n° 84 du 26 décembre 2024**, loi de finances 2025
n° 24-08, article 46 (modifiant l'article 100 du Code du timbre) et article 47
(créant l'article 258 quinquies) :

https://www.joradp.dz/FTP/jo-francais/2024/F2024084.pdf

Les montants sont définis par *classe du montant de quittance* avec un tarif
par tranche de 100 dinars ou fraction. Un minimum de perception s'applique.
Le paiement électronique bénéficie d'une disposition expresse de dispense.

La DGI a publié une nouvelle édition consolidée du Code du timbre en 2026 :
https://mfdgi.gov.dz/fr/a-propos/actu-fr/codes-fiscaux-fr

**Avant activation :** confronter l'édition 2026 aux articles cités, puis
obtenir une confirmation comptable du régime de l'entreprise et des types
de reçus et versements concernés.

## Anomalie détectée

Le circuit actuel de facturation utilise `1 %` et un plafond de `2 500 DA`,
avec une assiette liée au montant TTC facturé. Ce modèle n'est pas conforme à
la structure de l'article 100 modifié : il confond aussi une facture avec
une quittance de règlement réellement encaissé.

**Aucune modification du circuit Ventes en production** dans cette PR.
Il ne faut ni supprimer ni réécrire les factures anciennes.

## Nouveau prototype

`core/timbre_quittance.py` prépare un calcul :

- Uniquement sur le montant TTC d'un **règlement réellement constaté**.
- Classes selon le montant total, pas une progressivité marginale IRG.
- Toute fraction de tranche est une tranche entière.
- Minimum de perception et dispenses déterminés par un barème daté, sourcé,
  confirmé et unique.
- Pas de plafond ni taux par défaut.
- Deux moyens pris en charge : `ESPECES` et `ELECTRONIQUE` uniquement ;
  tous les autres nécessitent une classification métier et juridique.
- Renvoie uniquement `SIMULATION_NON_VALIDEE`, ne stocke ni facture ni paie.

## Prérequis avant utilisation réelle

1. Modéliser `reglements_clients` et leur liaison aux factures, paiements
   partiels, remboursements et reçus effectivement délivrés.
2. Classifier les quittances relevant de l'article 100-I et celles relevant
   d'autres dispositions.
3. Valider l'édition consolidée 2026, les dates d'effet et les exemptions.
4. Rattacher la règle réglementaire versionnée au registre,
   avec audit et approbation.
5. Vérifier les scénarios SQL transactionnels, idempotence et non-régression.
6. Activer ensuite simultanément l'interface et le calcul serveur ;
   ne jamais utiliser des taux de simulation comme valeurs de production.
