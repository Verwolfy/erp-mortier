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


## Renforcement des contrôles (lot de sécurisation)

Le lecteur SCF vérifie lui-même, **au moment de la requête**, la session
authentifiée, l'identifiant du compte actif et sa permission `SCF/lecture`.
L'interface ne peut plus lui transmettre une autorisation booléenne.

Les migrations 014 et 015 empêchent le changement de dates et d'identifiants
des périodes/exercices, y compris au moment de leur clôture. Un nouveau document
SCF ou un bulletin de paie n'est pas accepté sur une période déjà clôturée.

Ces protections SQL sont **encore des propositions non appliquées**. Leurs
tests Python et contrôles statiques ne remplacent pas des essais transactionnels
dans Supabase TEST. Aucun jeu de données réel n'a été modifié.


## Pré-audit de trésorerie avant passage SCF (29 octobre 2026)

Le module `core/rapprochement_finance_scf.py` et l'onglet
**Finance → Pré-audit Finance → SCF** contrôlent en lecture seule les
règlements provenant de la RPC Finance (`REGF-`) et les deux lignes
de comptabilité de trésorerie associées.

Pour chaque règlement, le contrôle exige :
- une référence unique et un statut `VALIDE` ;
- des dates identiques entre règlement et écritures ;
- deux comptes actifs et distincts, Banque/Caisse et Tiers correspondant
  au sens ENCAISSEMENT / DECAISSEMENT ;
- des montants avec deux décimales au plus, les débits et crédits exclusifs ;
- un montant débité et crédité égal au règlement enregistré ;
- aucun règlement sans écriture ni écriture RPC orpheline.

Les règlements historiques hors RPC sont **dénombrés mais non certifiés**.
Les comptes indiqués sont les numéros **saisis dans Finance** : ils ne sont
pas automatiquement validés dans le plan SCF et ne génèrent aucune écriture.

**Le passage réel en SCF reste distinct.** Il exigera un plan de comptes
actif homologué, un journal et un exercice ouverts, la détermination des
imputations et la non-duplication des écritures. Les états réglementaires
restent soumis à validation comptable.

## Correspondances Finance → SCF (29 octobre 2026)

**Pourquoi :** un numéro de compte bancaire ou de tiers saisi dans Finance
ne suffit pas à certifier son imputation selon le SCF.

**Comment :** dans l'onglet **Finance → Correspondances Finance / SCF**,
le contrôle à la demande compare les numéros *exactement*. Il signale
les comptes sans numéro, les numéros non référencés, les références
SCF inactives et les candidats à valider. Un numéro proche ou plus
long n'est jamais rapproché automatiquement.

La lecture du plan SCF est exhaustive (compteur exact) et réservée
aux utilisateurs habilités Finance. Le résultat est un diagnostic,
pas une migration, et n'autorise aucune écriture comptable.

Les comptes SCF intégrés lors de la migration 021 restent inactifs.
Pour les activer, il faudra disposer d'un plan approuvé et des règles
d'imputation correspondant au fonctionnement de l'entreprise.
